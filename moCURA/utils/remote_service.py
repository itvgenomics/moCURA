"""HTTP access to NCBI and BOLD with rate limits and an on-disk cache.

Rate limits (requests per second, shared by every coroutine of a service):

* NCBI E-utilities: 3 per second, or 10 per second when ``NCBI_API_KEY`` is set
  in the ``--env-file``;
* BOLD ID engine: the same limit as NCBI (BOLD has no published key);
* NCBI BLAST URL API: on top of the limit above, NCBI asks for at least 10 s
  between submissions and at most one status check per minute for each search
  (https://blast.ncbi.nlm.nih.gov/doc/blast-help/developerinfo.html).

Responses are cached under ``cache_dir`` keyed by the request, so a second run
does not query the services again. Network errors never stop moCURA: they are
logged and the caller receives ``None``.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


USER_AGENT = "moCURA (organelle assembly curation; https://github.com/itvgenomics)"


def read_env_file(**kwargs):
    """Read KEY=VALUE lines of a .env file. Missing file: empty dict and a warning."""

    path = kwargs.get("path")
    values = {}
    if not path:
        return values
    if not os.path.isfile(path):
        logging.warning("Environment file not found: %s", path)
        return values
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key.startswith("export "):
                key = key[len("export "):].strip()
            values[key] = value.strip().strip('"').strip("'")
    return values


class RateLimiter:
    """At most ``rate`` acquisitions per second across coroutines."""

    def __init__(self, rate):
        self.interval = 1.0 / float(rate)
        self.lock = asyncio.Lock()
        self.last = 0.0

    async def wait(self):
        async with self.lock:
            delay = self.last + self.interval - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            self.last = time.monotonic()


class RemoteService:
    """Rate-limited, cached HTTP client shared by the Phase 3 analyses."""

    def __init__(self, **kwargs):
        env = kwargs.get("env", {}) or {}
        self.api_key = env.get("NCBI_API_KEY") or None
        self.email = env.get("NCBI_EMAIL") or None
        self.rate = 10 if self.api_key else 3
        self.limiter = RateLimiter(self.rate)
        self.cache_dir = kwargs.get("cache_dir")
        self.refresh = bool(kwargs.get("refresh", False))
        self.timeout = int(kwargs.get("timeout", 120))
        self.retries = int(kwargs.get("retries", 3))
        self.blast_submit_interval = float(kwargs.get("blast_submit_interval", 10))
        self.blast_poll_interval = float(kwargs.get("blast_poll_interval", 60))
        self.blast_max_wait = float(kwargs.get("blast_max_wait", 1800))
        self.blast_lock = asyncio.Lock()
        self.blast_last_submit = 0.0
        self.requests = 0
        self.failures = 0
        if self.cache_dir:
            os.makedirs(self.cache_dir, exist_ok=True, mode=0o755)

    # ---------------------------------------------------------------- cache
    def cache_path(self, key):
        if not self.cache_dir:
            return None
        digest = hashlib.sha1(json.dumps(key, sort_keys=True).encode("utf-8")).hexdigest()
        return os.path.join(self.cache_dir, f"{digest}.json")

    def cache_get(self, key):
        path = self.cache_path(key)
        if self.refresh or not path or not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as handle:
                return json.load(handle)["body"]
        except (OSError, ValueError, KeyError):
            return None

    def cache_put(self, key, body):
        path = self.cache_path(key)
        if not path:
            return
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"key": key, "saved": time.strftime("%Y-%m-%d %H:%M:%S"), "body": body}, handle)

    # ----------------------------------------------------------------- http
    def _request_sync(self, url, data=None, headers=None):
        request = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, **(headers or {})})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")

    async def request(self, url, **kwargs):
        """GET (or POST with ``data``) under the rate limit. Returns (status, text) or (None, None)."""

        data = kwargs.get("data")
        headers = kwargs.get("headers")
        allow_404 = bool(kwargs.get("allow_404", False))
        for attempt in range(1, self.retries + 1):
            await self.limiter.wait()
            self.requests += 1
            try:
                return await asyncio.to_thread(self._request_sync, url, data, headers)
            except urllib.error.HTTPError as error:
                if error.code == 404 and allow_404:
                    return 404, ""
                retry = error.code in (429, 500, 502, 503, 504)
                logging.warning("HTTP %s from %s (attempt %d/%d)", error.code, url.split("?")[0], attempt, self.retries)
                if not retry:
                    break
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                logging.warning("Request to %s failed (attempt %d/%d): %s", url.split("?")[0], attempt, self.retries, error)
            await asyncio.sleep(min(60, 5 * attempt))
        self.failures += 1
        return None, None

    async def available(self):
        """One quick request to NCBI; False when the network or the service is unreachable."""

        try:
            await self.limiter.wait()
            status, _ = await asyncio.to_thread(self._request_sync, "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi?retmode=json&tool=moCURA")
            return status == 200
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            logging.warning("NCBI is not reachable: %s", error)
            return False

    # ---------------------------------------------------------- E-utilities
    def eutils_params(self, params):
        params = {**params, "tool": "moCURA"}
        if self.api_key:
            params["api_key"] = self.api_key
        if self.email:
            params["email"] = self.email
        return params

    async def eutils(self, endpoint, params, **kwargs):
        """Call an E-utility (esearch, efetch, esummary); cached by its parameters."""

        key = {"service": "eutils", "endpoint": endpoint, "params": params}
        cached = self.cache_get(key)
        if cached is not None:
            return cached
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/{endpoint}.fcgi"
        body = urllib.parse.urlencode(self.eutils_params(params)).encode("utf-8")
        status, text = await self.request(url, data=body)
        if status != 200 or text is None:
            return None
        if kwargs.get("as_json"):
            try:
                text = json.loads(text)
            except ValueError:
                logging.warning("E-utilities %s returned invalid JSON", endpoint)
                return None
        self.cache_put(key, text)
        return text

    # ---------------------------------------------------------------- BLAST
    async def blast(self, **kwargs):
        """Remote megablast of one sequence. Returns the JSON2 report or None."""

        sequence = kwargs.get("sequence")
        params = {
            "PROGRAM": "blastn",
            "MEGABLAST": "on",
            "DATABASE": kwargs.get("database", "core_nt"),
            "HITLIST_SIZE": str(kwargs.get("hitlist_size", 250)),
        }
        if kwargs.get("entrez_query"):
            params["ENTREZ_QUERY"] = kwargs["entrez_query"]
        key = {"service": "blast", "params": params, "sequence": sequence}
        cached = self.cache_get(key)
        if cached is not None:
            return cached

        async with self.blast_lock:
            delay = self.blast_last_submit + self.blast_submit_interval - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            submit = {**params, "CMD": "Put", "QUERY": sequence, "TOOL": "moCURA"}
            if self.email:
                submit["EMAIL"] = self.email
            status, text = await self.request("https://blast.ncbi.nlm.nih.gov/Blast.cgi", data=urllib.parse.urlencode(submit).encode("utf-8"))
            self.blast_last_submit = time.monotonic()
        rid = rtoe = None
        for line in (text or "").splitlines():
            line = line.strip()
            if line.startswith("RID ="):
                rid = line.split("=", 1)[1].strip()
            elif line.startswith("RTOE ="):
                rtoe = line.split("=", 1)[1].strip()
        if not rid:
            logging.warning("BLAST submission failed (no RID returned)")
            self.failures += 1
            return None

        waited = 0.0
        first_wait = max(10.0, min(float(rtoe or 30), self.blast_poll_interval))
        await asyncio.sleep(first_wait)
        waited += first_wait
        while waited <= self.blast_max_wait:
            status, text = await self.request(f"https://blast.ncbi.nlm.nih.gov/Blast.cgi?CMD=Get&FORMAT_OBJECT=SearchInfo&RID={rid}")
            state = None
            for line in (text or "").splitlines():
                if "Status=" in line:
                    state = line.split("Status=", 1)[1].strip()
            if state == "READY":
                break
            if state in ("FAILED", "UNKNOWN"):
                logging.warning("BLAST search %s ended with status %s", rid, state)
                self.failures += 1
                return None
            await asyncio.sleep(self.blast_poll_interval)
            waited += self.blast_poll_interval
        else:
            logging.warning("BLAST search %s did not finish within %d s", rid, self.blast_max_wait)
            self.failures += 1
            return None

        status, text = await self.request(f"https://blast.ncbi.nlm.nih.gov/Blast.cgi?CMD=Get&RID={rid}&FORMAT_TYPE=JSON2_S")
        try:
            report = json.loads(text)
        except (TypeError, ValueError):
            logging.warning("BLAST search %s returned no JSON report", rid)
            self.failures += 1
            return None
        report["rid"] = rid
        self.cache_put(key, report)
        return report

    # ----------------------------------------------------------------- BOLD
    async def bold(self, **kwargs):
        """BOLD v5 ID engine search of several sequences in one submission.

        ``sequences`` is {id: sequence}. Returns {id: result record} (None for a
        sequence whose search failed). Results are cached per sequence, and only
        uncached sequences are submitted, ``batch_size`` per request. BOLD answers
        503 when it is busy: the submission is retried after 30, 60, 90 s.
        """

        sequences = kwargs.get("sequences", {}) or {}
        params = {
            "db": kwargs.get("database", "public.tax-derep"),
            "mi": str(kwargs.get("min_identity", 0.9)),
            "mo": str(kwargs.get("min_overlap", 100)),
            "maxh": str(kwargs.get("max_hits", 100)),
            "order": "3",
        }
        # "format" 2: one result record per sequence (version 1 cached the list of a whole submission).
        key = lambda sequence: {"service": "bold", "format": 2, "params": params, "sequence": sequence}
        results, pending = {}, {}
        for identifier, sequence in sequences.items():
            cached = self.cache_get(key(sequence))
            if isinstance(cached, dict):
                results[identifier] = cached
            else:
                pending[identifier] = sequence
        items = list(pending.items())
        size = max(1, int(kwargs.get("batch_size", 20)))
        for start in range(0, len(items), size):
            batch = dict(items[start:start + size])
            records = await self.bold_submission(batch=batch, params=params, poll_interval=kwargs.get("poll_interval", 10),
                                                 max_wait=kwargs.get("max_wait", 1800), busy_retries=kwargs.get("busy_retries", 3))
            for identifier, sequence in batch.items():
                record = (records or {}).get(identifier)
                if record is not None:
                    self.cache_put(key(sequence), record)
                results[identifier] = record
        return results

    async def bold_submission(self, **kwargs):
        batch = kwargs.get("batch")
        params = kwargs.get("params")
        boundary = uuid.uuid4().hex
        fasta = "".join(f">{identifier}\n{sequence}\n" for identifier, sequence in batch.items())
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"fasta_file\"; filename=\"query.fas\"\r\n"
            f"Content-Type: text/plain\r\n\r\n{fasta}\r\n--{boundary}--\r\n"
        ).encode("utf-8")
        url = "https://id.boldsystems.org/submission?" + urllib.parse.urlencode(params)
        sub_id = None
        for attempt in range(int(kwargs.get("busy_retries", 3)) + 1):
            status, text = await self.request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
            try:
                sub_id = json.loads(text)["sub_id"]
                break
            except (TypeError, ValueError, KeyError):
                wait = 30 * (attempt + 1)
                logging.warning("BOLD is busy or refused the submission; retrying in %d s", wait)
                await asyncio.sleep(wait)
        if not sub_id:
            logging.warning("BOLD submission failed for %d sequence(s)", len(batch))
            self.failures += 1
            return None

        waited = 0.0
        poll = float(kwargs.get("poll_interval", 10))
        while waited <= float(kwargs.get("max_wait", 1800)):
            await asyncio.sleep(poll)
            waited += poll
            status, text = await self.request(f"https://id.boldsystems.org/submission/results/{sub_id}", allow_404=True)
            if status == 200 and text and text.strip():
                try:
                    records = [json.loads(line) for line in text.splitlines() if line.strip()]
                except ValueError:
                    continue
                found = {str(record.get("seqid")): record for record in records}
                if all(identifier in found for identifier in batch):
                    return found
        logging.warning("BOLD search %s did not finish in time", sub_id)
        self.failures += 1
        return None
