import base64
import html
import json
import logging
import mimetypes
import os

from .prepare_html_report_data import prepare_html_report_data


def _project_roots():
  """Return candidate roots for asset resolution.

  package_root: .../moCURA
  repository_or_container_root: parent of package_root
  """

  package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  repository_or_container_root = os.path.dirname(package_root)
  return package_root, repository_or_container_root


def _resolve_asset_path(path):
  """Resolve asset paths across local and container layouts.

  Supports absolute paths and relative paths against:
  1) repository/container root
  2) package root
  3) current working directory
  """

  if not path:
    return None

  candidate = str(path)
  if os.path.isabs(candidate):
    return candidate if os.path.isfile(candidate) else None

  package_root, repository_or_container_root = _project_roots()
  for root in (repository_or_container_root, package_root, os.getcwd()):
    resolved = os.path.join(root, candidate)
    if os.path.isfile(resolved):
      return resolved

  return None


def image_data_uri(path):
    if not path or not os.path.isfile(path):
        return None
    mime_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    with open(path, "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def load_embedded_basemap():
  basemap_path = _resolve_asset_path(os.path.join("assets", "world_lowres.geojson"))
  if not basemap_path or not os.path.isfile(basemap_path):
    return {"type": "FeatureCollection", "features": []}
  try:
    with open(basemap_path, "r", encoding="utf-8") as handle:
      return json.load(handle)
  except Exception as error:
    logging.warning("Could not load embedded vector basemap: %s", error)
    return {"type": "FeatureCollection", "features": []}


def build_logo_html(config):
  if not config:
    return ""

  logo_path = config.get("logo_path")
  if not logo_path:
    return ""

  resolved = _resolve_asset_path(logo_path)
  if not resolved:
    logging.warning("Logo file was not found for the HTML report: %s", logo_path)
    return ""

  alt = html.escape(str(config.get("logo_alt", "moCURA logo")))

  if str(resolved).lower().endswith(".svg"):
    with open(resolved, "r", encoding="utf-8") as handle:
      svg = handle.read()
    svg = svg.replace('<?xml version="1.0" encoding="UTF-8" standalone="no"?>', "", 1).strip()
    return f'<div class="header-logo-svg" role="img" aria-label="{alt}">{svg}</div>'

  data_uri = image_data_uri(resolved)
  if not data_uri:
    return ""
  return f'<img class="header-logo" src="{data_uri}" alt="{alt}">'


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__REPORT_TITLE__</title>
<link id="maplibreStylesheet" rel="stylesheet" href="https://cdn.jsdelivr.net/npm/maplibre-gl@5.13.0/dist/maplibre-gl.css" onerror="this.onerror=null;this.href='https://unpkg.com/maplibre-gl@5.13.0/dist/maplibre-gl.css';" />
<style>
:root {
  --bg: #f8fafc;
  --panel: #ffffff;
  --text: #202020;
  --muted: #64748b;
  --border: #dbe3ea;
  --brand: #0173B2;
  --brand-soft: #e8f3f9;
  --secondary: #029E73;
  --accent: #E76F51;
  --range: #B0E4CC;
  --stripe: #EEEEEE;
  --danger-bg: #fef2f2;
  --danger: #991b1b;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { margin: 0; background: var(--bg); color: var(--text); font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
button, select, input { font: inherit; }
button { cursor: pointer; }
a { color: inherit; text-decoration: none; }
.shell { max-width: 1900px; margin: 0 auto; padding: 24px; }
.header-wrap { display: flex; gap: 18px; align-items: center; }
.header-brand { flex: 0 0 auto; display: flex; align-items: center; justify-content: center; }
.header-logo { display: block; width: 180px; max-width: 26vw; height: auto; object-fit: contain; }
.header-logo-svg { width: 180px; max-width: 26vw; line-height: 0; }
.header-logo-svg svg { display: block; width: 100%; height: auto; }
.header-text { min-width: 0; }
.eyebrow { color: var(--brand); text-transform: uppercase; letter-spacing: .2em; font-size: 12px; font-weight: 700; }
h1 { margin: 4px 0 0; font-size: 30px; color: #020617; }
.subtitle { margin-top: 8px; color: var(--muted); font-size: 14px; }
.tabs { display: flex; flex-wrap: wrap; gap: 8px; overflow: visible; padding: 18px 0 12px; border-bottom: 1px solid var(--border); align-items: center; }
.project-tab { white-space: nowrap; border: 1px solid var(--border); background: white; border-radius: 12px; padding: 9px 14px; color: #475569; font-weight: 600; flex: 0 0 auto; }
.project-tab.active { background: var(--brand); border-color: var(--brand); color: white; }
.project-tab.all-tab.active { background: #0f766e; border-color: #0f766e; }
.filters { position: sticky; top: 0; z-index: 5000; background: rgba(248,250,252,.97); backdrop-filter: blur(8px); border-bottom: 1px solid var(--border); margin: 0 -24px; padding: 10px 24px 12px; }
.sticky-filter-row { display: grid; grid-template-columns: minmax(0,1fr); gap: 0; align-items: end; transition: grid-template-columns .18s ease, gap .18s ease; }
.sticky-logo { display: none; align-items: center; justify-content: flex-start; min-height: 48px; overflow: visible; }
.filters.is-stuck .sticky-filter-row { grid-template-columns: 104px minmax(0,1fr); gap: 14px; }
.filters.is-stuck .sticky-logo { display: flex; }
.sticky-logo .header-logo, .sticky-logo .header-logo-svg { width: 92px; max-width: 92px; }
.sticky-logo .header-logo-svg svg { width: 100%; height: auto; }
.filter-grid { display: grid; grid-template-columns: repeat(4, minmax(170px, 1fr)) auto; gap: 12px; align-items: end; }
.filter-label { display: flex; gap: 5px; align-items: center; margin-bottom: 4px; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; font-size: 11px; font-weight: 700; }
input[type="search"] { width: 100%; border: 1px solid #cbd5e1; background: white; border-radius: 10px; padding: 9px 11px; color: var(--text); outline: none; }
input[type="search"]:focus { border-color: var(--brand); box-shadow: 0 0 0 3px rgba(1,115,178,.12); }
.multi-select { position: relative; }
.multi-trigger { width: 100%; min-height: 40px; display: flex; align-items: center; justify-content: space-between; gap: 8px; border: 1px solid #cbd5e1; background: white; border-radius: 10px; padding: 8px 10px; color: #334155; text-align: left; }
.multi-trigger:hover, .multi-select.open .multi-trigger { border-color: var(--brand); box-shadow: 0 0 0 3px rgba(1,115,178,.10); }
.multi-trigger-label { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.multi-caret { color: #94a3b8; font-size: 11px; }
.multi-menu { display: none; position: absolute; z-index: 80; left: 0; right: 0; top: calc(100% + 5px); min-width: 250px; max-height: 340px; border: 1px solid #cbd5e1; background: white; border-radius: 12px; box-shadow: 0 18px 45px rgba(15,23,42,.16); padding: 8px; }
.multi-select.open .multi-menu { display: block; }
.multi-search { width: 100%; margin-bottom: 7px; }
.multi-actions { display: flex; gap: 6px; margin-bottom: 7px; }
.multi-actions button { flex: 1; border: 1px solid #dbe3ea; background: #f8fafc; border-radius: 8px; padding: 6px 8px; color: #475569; font-size: 11px; }
.multi-options { max-height: 230px; overflow: auto; }
.multi-option { display: flex; align-items: center; gap: 8px; padding: 7px 6px; border-radius: 7px; color: #334155; font-size: 12px; cursor: pointer; }
.multi-option:hover { background: var(--brand-soft); }
.multi-option input { accent-color: var(--brand); }
.multi-empty { padding: 10px; color: #94a3b8; font-size: 12px; text-align: center; }
.reset { border: 1px solid #b91c1c; background: #dc2626; border-radius: 10px; padding: 9px 14px; color: white; font-weight: 750; box-shadow: 0 1px 2px rgba(127,29,29,.18); }
.reset:hover { background: #b91c1c; border-color: #991b1b; }
.filter-summary { margin-top: 8px; color: var(--muted); font-size: 12px; }
.nav { display: flex; gap: 7px; overflow-x: auto; margin-top: 10px; padding-bottom: 2px; align-items: center; }
.nav a { white-space: nowrap; padding: 8px 12px; border: 1px solid #dbe3ea; background: #ffffff; border-radius: 999px; color: #475569; font-size: 12px; font-weight: 650; box-shadow: 0 1px 2px rgba(15,23,42,.04); }
.nav a:hover { border-color: var(--brand); background: var(--brand-soft); color: var(--brand); }
.nav a.active { border-color: var(--brand); background: var(--brand); color: white; }
.species-toggle { margin-left: auto; white-space: nowrap; display: inline-flex; align-items: center; gap: 9px; padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 999px; background: #fff; color: #475569; font-size: 12px; font-weight: 700; cursor: pointer; transition: border-color .15s ease, background .15s ease, box-shadow .15s ease; }
.species-toggle:hover { border-color: #93c5fd; background: #f8fbff; }
.species-toggle:has(input:checked) { border-color: var(--brand); background: var(--brand-soft); color: #075985; box-shadow: 0 0 0 3px rgba(1,115,178,.08); }
.species-toggle input,
.marker-category-option input,
.map-marker-option input,
.map-network-toggle input,
.multi-option input[type="checkbox"] { appearance: none; -webkit-appearance: none; flex: 0 0 auto; width: 18px; height: 18px; margin: 0; border: 1.5px solid #94a3b8; border-radius: 5px; background-color: #fff; background-position: center; background-repeat: no-repeat; background-size: 12px 12px; cursor: pointer; transition: background-color .15s ease, border-color .15s ease, box-shadow .15s ease, transform .1s ease; }
.species-toggle input:checked,
.marker-category-option input:checked,
.map-marker-option input:checked,
.map-network-toggle input:checked,
.multi-option input[type="checkbox"]:checked { border-color: var(--brand); background-color: var(--brand); background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M3 8.4 6.3 12 13 4.6' fill='none' stroke='white' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E"); box-shadow: 0 0 0 3px rgba(1,115,178,.10); }
.species-toggle input:active,
.marker-category-option input:active,
.map-marker-option input:active,
.map-network-toggle input:active,
.multi-option input[type="checkbox"]:active { transform: scale(.92); }
.marker-category-controls { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 8px; }
.marker-category-option { display: inline-flex; align-items: center; gap: 8px; min-height: 36px; padding: 7px 12px; border: 1px solid #cbd5e1; border-radius: 10px; background: #fff; color: #475569; font-size: 12px; font-weight: 700; cursor: pointer; transition: border-color .15s ease, background .15s ease, box-shadow .15s ease; }
.marker-category-option:hover { border-color: #93c5fd; background: #f8fbff; }
.marker-category-option:has(input:checked) { border-color: var(--brand); background: var(--brand-soft); color: #075985; box-shadow: 0 0 0 3px rgba(1,115,178,.07); }
.multi-option:has(input:checked) { background: var(--brand-soft); color: #075985; font-weight: 650; }
.section { margin-top: 30px; scroll-margin-top: 150px; }
.section h2 { margin: 0; color: #020617; font-size: 20px; }
.section-note { margin-top: 4px; color: var(--muted); font-size: 13px; }
.metrics { display: grid; grid-template-columns: repeat(6, minmax(0,1fr)); gap: 12px; }
.card { border: 1px solid var(--border); background: var(--panel); border-radius: 16px; box-shadow: 0 1px 2px rgba(15,23,42,.05); }
.metric { padding: 16px; }
.metric-label { display: flex; gap: 6px; align-items: center; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; font-size: 11px; }
.metric-value { margin-top: 5px; color: #020617; font-size: 24px; font-weight: 700; }
.info-dot { display: inline-grid; place-items: center; width: 17px; height: 17px; border-radius: 50%; background: #e2e8f0; color: #475569; font-size: 10px; font-weight: 800; cursor: help; text-transform: none; letter-spacing: 0; }
.info-grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 12px; margin-top: 12px; }
.info-card { padding: 14px 15px; border-left: 4px solid var(--brand); }
.info-card:nth-child(2) { border-left-color: var(--secondary); }
.info-card:nth-child(3) { border-left-color: var(--accent); }
.info-title { font-size: 13px; font-weight: 700; color: #0f172a; }
.info-copy { margin-top: 4px; color: var(--muted); font-size: 12px; line-height: 1.45; }
.chart-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 16px; margin-top: 16px; }
.pilon-grid.stacked { grid-template-columns: 1fr; }
.pilon-grid.stacked .chart { min-height: 520px; }
.assembly-metric-grid { display: grid; grid-template-columns: minmax(240px,320px) repeat(4,minmax(0,1fr)); gap: 14px; margin-top: 14px; align-items: stretch; }
.assembly-species-card, .assembly-metric-card { padding: 10px; min-width: 0; overflow: hidden; display: flex; flex-direction: column; height: 100%; }
.assembly-species-card .chart-subtitle, .assembly-metric-card .chart-subtitle { min-height: 34px; }
.assembly-species-chart, .assembly-metric-chart { width: 100%; overflow: hidden; flex: 1 1 auto; min-height: 470px; }
.assembly-table-help { margin-top: 7px; color: var(--muted); font-size: 11px; display: flex; align-items: center; gap: 6px; }
.assembly-table-help svg { width: 15px; height: 15px; stroke: var(--brand); flex: 0 0 auto; }
.assembly-legend { margin-top: 12px; padding: 10px 12px; display: flex; flex-wrap: wrap; gap: 8px 14px; align-items: center; }
.legend-item { display: inline-flex; align-items: center; gap: 6px; color: #475569; font-size: 11px; }
.legend-seed-dot { width: 12px; height: 12px; border-radius: 50%; border: 1px solid #202020; }
.legend-range-line { width: 28px; height: 4px; background: var(--range); }
.chart-card { padding: 14px; min-width: 0; }
.chart-title { font-weight: 650; color: #0f172a; margin-bottom: 2px; }
.chart-subtitle { color: var(--muted); font-size: 12px; margin-bottom: 8px; }
.chart { min-height: 410px; width: 100%; overflow: hidden; }
.chart svg { display: block; width: 100%; height: auto; }
.tooltip { position: fixed; z-index: 100; pointer-events: none; opacity: 0; background: rgba(15,23,42,.94); color: white; padding: 8px 10px; border-radius: 8px; font-size: 12px; line-height: 1.45; max-width: 320px; }
.table-card { margin-top: 16px; overflow: hidden; }
.table-toolbar { display: flex; justify-content: space-between; align-items: end; gap: 16px; padding: 14px; border-bottom: 1px solid var(--border); }
.table-title { white-space: nowrap; }
.table-tools { display: flex; gap: 12px; align-items: end; flex-wrap: wrap; justify-content: flex-end; }
.table-search-control { min-width: 520px; max-width: 760px; flex: 1 1 520px; }
.table-search-control .filter-label { justify-content: flex-start; }
.table-search-wrap { position: relative; width: 100%; }
.table-search-wrap svg { position: absolute; left: 11px; top: 50%; transform: translateY(-50%); width: 16px; height: 16px; stroke: #64748b; pointer-events: none; }
.table-search-wrap input[type="search"] { min-width: 520px; width: 100%; padding-left: 36px; }
.table-width-control input[type="range"] { width: 190px; accent-color: var(--brand); }
.table-scroll { cursor: grab; }
.table-scroll.dragging { cursor: grabbing; user-select: none; }
.table-scroll table, .table-scroll th, .table-scroll td { white-space: nowrap; }
.assembly-table thead th:first-child, .assembly-table tbody td:first-child, .assembly-table thead th:nth-child(2), .assembly-table tbody td:nth-child(2) { text-align: left; }
.table-title { color: #0f172a; font-weight: 650; }
.table-count { margin-top: 3px; color: var(--muted); font-size: 12px; }
.table-scroll { max-height: 650px; overflow: auto; }
.resizable-table { table-layout: fixed; width: max-content; min-width: 100%; border-collapse: collapse; }
.resizable-table th { position: sticky; overflow: visible; }
.resizable-table th.sticky-col, .resizable-table td.sticky-col { position: sticky; z-index: 5; }
.resizable-table thead th.sticky-col { background: #e2e8f0; z-index: 7; }
.resizable-table tbody td.sticky-col { box-shadow: 1px 0 0 #dbe3ea; }
.column-resizer { position: absolute; top: 0; right: -4px; width: 9px; height: 100%; cursor: col-resize; user-select: none; z-index: 8; }
.column-resizer:hover, .column-resizer.active { background: rgba(1,115,178,.22); }
table { width: 100%; min-width: 1450px; border-collapse: collapse; }
thead th { position: sticky; top: 0; z-index: 4; background: #e2e8f0; color: #475569; text-align: left; text-transform: uppercase; letter-spacing: .035em; font-size: 11px; padding: 9px 10px; white-space: nowrap; }
tbody td { border-top: 1px solid var(--border); padding: 8px 10px; vertical-align: top; font-size: 13px; white-space: nowrap; }
tbody tr:nth-child(odd) { background: #fff; }
tbody tr:nth-child(even) { background: var(--stripe); }
tbody tr:hover { background: var(--brand-soft); }
.assembly-table thead th, .assembly-table tbody td { text-align: center; vertical-align: middle; }
.assembly-table tbody tr.project-start td { border-top: 22px solid var(--bg); }
.assembly-table tbody tr.project-start td:first-child { box-shadow: inset 0 2px 0 #cbd5e1; }
.assembly-table tbody tr:nth-child(odd) td.sticky-col { background: #fff; }
.assembly-table tbody tr:nth-child(even) td.sticky-col { background: var(--stripe); }
.assembly-table tbody tr:hover td.sticky-col { background: var(--brand-soft); }
.circularized-cell { padding: 0 !important; font-weight: 750; }
.circularized-cell.yes { background: #b8e3d5 !important; color: #05624b; }
.circularized-cell.no { background: #e5e7eb !important; color: #64748b; }
.circularized-cell > span { display: block; width: 100%; height: 100%; padding: 10px 8px; }
.data-bar-cell { position: relative; overflow: hidden; padding: 0 !important; min-width: 118px; }
.data-bar-cell .cell-bar { position: absolute; inset: 0 auto 0 0; width: var(--bar-width,0%); background: var(--bar-color,rgba(1,115,178,.24)); pointer-events: none; }
.data-bar-cell .cell-value { position: relative; z-index: 2; display: block; padding: 10px 8px; font-variant-numeric: tabular-nums; }
.marker-scale-legend { margin: 8px 0 4px; color: var(--muted); font-size: 11px; }
.badge { display: inline-block; padding: 3px 8px; border-radius: 999px; font-size: 11px; font-weight: 650; }
.badge.yes { background: #d1fae5; color: #047857; }
.badge.no { background: #e2e8f0; color: #64748b; }
code { word-break: break-all; font-size: 11px; }
.assembly-select { margin-top: 14px; max-width: 720px; }
.genome-scroll { overflow: auto; max-height: 900px; }
.assembly-interaction-note { margin-top: 12px; padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 10px; background: #f8fafc; color: #475569; font-size: 12px; line-height: 1.45; }
.assembly-interaction-note strong { color: #0f172a; }
.marker-heatmap-card { margin-top: 14px; width: 100%; }
.marker-heatmap-scroll { overflow: auto; max-height: 940px; }
.species-label { font-style: italic; font-weight: 400; }
.map-analysis-panel { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 14px; align-items: start; margin: 14px 0; padding: 13px 14px; border: 1px solid var(--border); border-radius: 14px; background: #fff; }
.map-analysis-title { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; color: #0f172a; font-size: 12px; font-weight: 800; }
.map-analysis-copy { color: var(--muted); font-size: 11px; line-height: 1.45; margin-bottom: 9px; }
.map-marker-options { display: flex; flex-wrap: wrap; gap: 7px; }
.map-marker-option, .map-network-toggle { display: inline-flex; align-items: center; gap: 7px; min-height: 34px; padding: 6px 10px; border: 1px solid #cbd5e1; border-radius: 999px; background: #fff; color: #475569; font-size: 11px; font-weight: 750; cursor: pointer; transition: border-color .15s ease, background .15s ease, box-shadow .15s ease; }
.map-marker-option:hover, .map-network-toggle:hover { border-color: #93c5fd; background: #f8fbff; }
.map-marker-option:has(input:checked), .map-network-toggle:has(input:checked) { border-color: var(--brand); background: var(--brand-soft); color: #075985; box-shadow: 0 0 0 3px rgba(1,115,178,.07); }
.map-marker-actions { display: flex; gap: 7px; flex-wrap: wrap; margin-bottom: 8px; }
.map-marker-action { border: 1px solid #cbd5e1; border-radius: 8px; background: #f8fafc; color: #475569; padding: 5px 9px; font-size: 10px; font-weight: 750; cursor: pointer; }
.map-marker-action:hover { border-color: #93c5fd; background: #eff6ff; }
.map-network-column { min-width: 220px; max-width: 330px; }
.map-network-help { margin-top: 8px; color: var(--muted); font-size: 10px; line-height: 1.45; }
.map-card { position: relative; z-index: 0; isolation: isolate; contain: paint; padding: 0; overflow: hidden; }
#samplingMap { position: relative; z-index: 0; isolation: isolate; width: 100%; height: 560px; min-height: 560px; overflow: hidden; background: #e9eef2; }
.haplotype-network-panel { position: absolute; right: 14px; bottom: 42px; z-index: 8; width: min(390px,calc(100% - 28px)); max-height: 360px; overflow: hidden; border: 1px solid #cbd5e1; border-radius: 14px; background: rgba(255,255,255,.96); box-shadow: 0 12px 30px rgba(15,23,42,.18); backdrop-filter: blur(7px); display: none; }
.haplotype-network-panel.active { display: block; }
.haplotype-network-head { display: flex; justify-content: space-between; gap: 10px; padding: 10px 12px 8px; border-bottom: 1px solid #e2e8f0; }
.haplotype-network-title { color: #0f172a; font-size: 12px; font-weight: 800; }
.haplotype-network-copy { margin-top: 2px; color: var(--muted); font-size: 9.5px; line-height: 1.35; }
.haplotype-network-body { padding: 6px 8px 8px; }
.haplotype-network-body svg { display: block; width: 100%; height: auto; }
.haplotype-network-empty { padding: 18px; color: var(--muted); font-size: 11px; text-align: center; }
.haplotype-node { cursor: pointer; }
@media (max-width: 900px) { .map-analysis-panel { grid-template-columns: 1fr; } .map-network-column { min-width: 0; max-width: none; } .haplotype-network-panel { left: 14px; right: 14px; width: auto; } }
#samplingMap .maplibregl-map { font-family: inherit; }
#samplingMap .maplibregl-canvas-container, #samplingMap .maplibregl-canvas { z-index: 0; }
#samplingMap .maplibregl-control-container { position: relative; z-index: 4; }
#samplingMap .maplibregl-popup { z-index: 6; }
#samplingMap .maplibregl-popup-content { margin: 0; padding: 12px 14px; line-height: 1.45; font-family: inherit; font-size: 11px; border-radius: 10px; }
#samplingMap .maplibregl-ctrl-group { overflow: hidden; border-radius: 9px; box-shadow: 0 2px 8px rgba(15,23,42,.14); }
#samplingMap canvas { outline: none; }
.map-controls { position: absolute; right: 12px; top: 12px; z-index: 7; display: grid; gap: 6px; }
.map-controls button { width: 34px; height: 34px; border: 1px solid #cbd5e1; border-radius: 8px; background: rgba(255,255,255,.95); color: #334155; font-weight: 800; font-size: 17px; box-shadow: 0 2px 8px rgba(15,23,42,.12); cursor: pointer; }
.map-controls button:hover { background: #eff6ff; border-color: #93c5fd; }
.map-overlay { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
.map-overlay .map-point { pointer-events: auto; cursor: pointer; }
.map-attribution { position: absolute; right: 6px; bottom: 5px; z-index: 5; background: rgba(255,255,255,.88); padding: 3px 6px; border-radius: 5px; font-size: 9px; color: #475569; }
.map-legend { position: absolute; left: 8px; bottom: 8px; z-index: 5; background: rgba(255,255,255,.92); border: 1px solid #dbe3ea; border-radius: 8px; padding: 7px 9px; font-size: 10px; color: #475569; }
.map-note { padding: 10px 14px; color: var(--muted); font-size: 12px; border-top: 1px solid var(--border); }
.report-footer { margin-top: 34px; background: #0f172a; color: #e2e8f0; border-radius: 18px 18px 0 0; overflow: hidden; }
.footer-brand { display: flex; justify-content: center; align-items: center; padding: 30px 28px 10px; }
.footer-logo { display: flex; justify-content: center; align-items: center; width: 100%; }
.footer-logo .header-logo, .footer-logo .header-logo-svg { width: 280px; max-width: min(280px,70vw); }
.footer-logo .header-logo-svg svg { width: 100%; height: auto; }
.report-footer-grid { display: grid; grid-template-columns: 1fr 1.2fr 1fr; gap: 28px; padding: 18px 28px 30px; }
.report-footer-title { color: white; font-weight: 800; margin-bottom: 10px; font-size: 14px; }
.report-footer-copy { color: #cbd5e1; font-size: 13px; line-height: 1.6; }
.report-footer-credit { border-top: 1px solid rgba(203,213,225,.18); padding: 14px 24px 18px; text-align: center; color: #cbd5e1; font-size: 12px; letter-spacing: .01em; }
.image-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 16px; margin-top: 14px; }
.snp-grid { display: grid; grid-template-columns: repeat(auto-fit,minmax(min(100%,620px),1fr)); grid-auto-flow: dense; gap: 18px; margin-top: 14px; align-items: start; }
.snp-card { overflow: hidden; min-width: 0; }
.snp-card-wide { grid-column: 1 / -1; }
.snp-card-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 11px 14px; border-bottom: 1px solid var(--border); background: #f8fafc; }
.snp-card-title { color: #0f172a; font-size: 14px; font-weight: 700; }
.snp-card-meta { color: var(--muted); font-size: 11px; }
.snp-chart-scroll { overflow-x: auto; overflow-y: hidden; padding: 8px 8px 2px; }
.snp-chart-scroll svg { max-width: none; display: block; }
.snp-chart-scroll.compact { overflow-x: hidden; }
.snp-chart-scroll.compact svg { max-width: 100%; width: 100%; }
.file-grid { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 12px; margin-top: 14px; }
.file-card { padding: 13px; }
.file-name { font-size: 13px; font-weight: 650; }
.file-path { margin-top: 4px; color: var(--muted); word-break: break-all; font-size: 11px; }
.empty { min-height: 240px; display: grid; place-items: center; color: #94a3b8; font-size: 13px; }
#errorBox { display: none; margin: 16px 0; padding: 14px; border: 1px solid #fecaca; border-radius: 12px; background: var(--danger-bg); color: var(--danger); white-space: pre-wrap; }
.axis text { fill: #64748b; font-size: 10px; }
.axis path, .axis line { stroke: #cbd5e1; }
.grid-line line { stroke: #e2e8f0; stroke-opacity: .75; }
.grid-line path { stroke-width: 0; }
.legend { font-size: 11px; fill: #475569; }
@media (max-width: 1200px) {
  .metrics { grid-template-columns: repeat(3,minmax(0,1fr)); }
  .sticky-filter-row { grid-template-columns: 78px minmax(0,1fr); }
  .sticky-logo .header-logo, .sticky-logo .header-logo-svg { width: 68px; max-width: 68px; }
  .filter-grid { grid-template-columns: repeat(2,minmax(0,1fr)); }
  .assembly-metric-grid { grid-template-columns: repeat(2,minmax(0,1fr)); }
  .info-grid { grid-template-columns: 1fr; }
  .file-grid { grid-template-columns: repeat(2,minmax(0,1fr)); }
}
@media (max-width: 780px) {
  .shell { padding: 14px; }
  .filters { margin: 0 -14px; padding: 10px 14px; }
  .sticky-filter-row { grid-template-columns: 1fr; }
  .sticky-logo { display: none; }
  .metrics, .chart-grid, .assembly-metric-grid, .image-grid, .snp-grid, .file-grid, .filter-grid { grid-template-columns: 1fr; }
  .table-toolbar { flex-direction: column; align-items: stretch; }
}
</style>
</head>
<body>
<div class="shell">
  <div id="errorBox"></div>

  <header>
    <div class="header-wrap">
      <div class="header-brand">__LOGO_HTML__</div>
      <div class="header-text">
        <div class="eyebrow">moCURA</div>
        <h1>__REPORT_TITLE__</h1>
        <div class="subtitle">Interactive organelle assembly report.</div>
      </div>
    </div>
    <div id="projectTabs" class="tabs"></div>
  </header>

  <div id="filterStickySentinel" aria-hidden="true"></div>
  <div id="filterBar" class="filters">
    <div class="sticky-filter-row">
      <div class="sticky-logo">__LOGO_HTML__</div>
      <div class="filter-grid">
        <div><span class="filter-label">Seed <span class="info-dot" data-tooltip="Select one or more seed inputs. Use the search box inside the menu when many seeds are available.">i</span></span><div id="seedFilter" class="multi-select"></div></div>
        <div><span class="filter-label">K-mer <span class="info-dot" data-tooltip="Select one or more K-mer values. Multiple values can be compared simultaneously.">i</span></span><div id="kmerFilter" class="multi-select"></div></div>
        <div><span class="filter-label">Assembly status <span class="info-dot" data-tooltip="Choose circularized, non-circularized, or both assembly states.">i</span></span><div id="statusFilter" class="multi-select"></div></div>
        <div><span class="filter-label">Tandem repeats <span class="info-dot" data-tooltip="Filter runs according to whether TRF detected tandem repeats.">i</span></span><div id="repeatFilter" class="multi-select"></div></div>
        <button id="resetFilters" class="reset">Reset filters</button>
      </div>
    </div>
    <div id="filterSummary" class="filter-summary"></div>
    <nav class="nav" aria-label="Report sections">
      <a class="nav-link active" href="#overview" data-tooltip="Summary cards and guidance for the current filtered view.">Overview</a>
      <a class="nav-link" href="#assemblies" data-tooltip="Linked NOVOPlasty assembly metrics. Hovering one run highlights the same run in all four panels.">Assemblies</a>
      <a class="nav-link" href="#pilon" data-tooltip="Interactive polishing metrics from Pilon.">Pilon</a>
      <a class="nav-link" href="#genome" data-tooltip="Marker and tandem-repeat positions for every assembly that passes the filters.">Genome</a>
      <a class="nav-link" href="#markers" data-tooltip="Marker lengths with an independent min–max color scale for every marker column.">Markers</a>
      <a class="nav-link" href="#repeats" data-tooltip="TRF repeat families, genomic context and comparative table.">Repeats</a>
      <a class="nav-link" href="#snps" data-tooltip="True-SNP matrices rendered directly with D3 in a Snipit-like layout.">SNPs</a>
      <a class="nav-link" href="#map" data-tooltip="Sampling localities with SNP differences on the embedded geographic basemap.">Map</a>
      <label class="species-toggle" data-tooltip-html="When enabled, species labels are shortened from <em>Homo sapiens</em> to <em>H. sapiens</em> throughout the report. It is disabled by default."><input id="abbreviateSpecies" type="checkbox"> Abbreviate species <span class="info-dot">i</span></label>
    </nav>
  </div>

  <section id="overview" class="section">
    <div class="metrics">
      <div class="card metric"><div class="metric-label">Projects <span class="info-dot" data-tooltip="Number of projects represented after applying the current filters.">i</span></div><div id="metricProjects" class="metric-value"></div></div>
      <div class="card metric"><div class="metric-label">Runs <span class="info-dot" data-tooltip="Number of NOVOPlasty project, seed and K-mer combinations in the current view.">i</span></div><div id="metricAssemblies" class="metric-value"></div></div>
      <div class="card metric"><div class="metric-label">Circularized <span class="info-dot" data-tooltip="Runs reported as circularized by the assembly workflow.">i</span></div><div id="metricCircularized" class="metric-value"></div></div>
      <div class="card metric"><div class="metric-label">Rotated genomes <span class="info-dot" data-tooltip="Rotated GenBank assemblies available for marker and genome-position analyses.">i</span></div><div id="metricGenbanks" class="metric-value"></div></div>
      <div class="card metric"><div class="metric-label">TRF repeats <span class="info-dot" data-tooltip="Number of tandem-repeat records detected by TRF in the filtered assemblies.">i</span></div><div id="metricRepeats" class="metric-value"></div></div>
      <div class="card metric"><div class="metric-label">Median coverage <span class="info-dot" data-tooltip="Median NOVOPlasty average organelle coverage for the filtered runs.">i</span></div><div id="metricCoverage" class="metric-value"></div></div>
    </div>
    <div class="info-grid">
      <div class="card info-card"><div class="info-title">Multiple filters</div><div class="info-copy">Seed, K-mer, assembly status and repeat status support multiple selections. Search inside each filter to quickly find values in large projects.</div></div>
      <div class="card info-card"><div class="info-title">Linked assembly plots</div><div class="info-copy">Hover a point in any assembly panel. The same project, seed and K-mer run remains at 100% opacity in every panel while all other runs fade to 25%.</div></div>
      <div class="card info-card"><div class="info-title">Genome and SNP detail</div><div class="info-copy">Genome structure shows every filtered rotated assembly. SNP matrices are D3 SVG views generated from true-SNP tables and remain filter-aware.</div></div>
    </div>
  </section>

  <section id="assemblies" class="section">
    <h2>Assembly overview <span class="info-dot" data-tooltip="Interactive HTML version of the NOVOPlasty four-panel summary. Seed is encoded by color, K-mer by marker shape, and genome ranges by the green band.">i</span></h2>
    <div id="assemblySubtitle" class="section-note"></div>
    <div id="assemblyInteractionStatus" class="assembly-interaction-note"><strong>Interactive selection:</strong> click any point to isolate that same Project + Seed + K-mer combination across all four plots. Click the selected point again to restore all values.</div>
    <div id="assemblyLegend" class="card assembly-legend"></div>
    <div class="assembly-metric-grid">
      <div class="card assembly-species-card"><div class="chart-title">Project / species</div><div class="chart-subtitle">Species names are listed in a dedicated column so the four metric plots can use the full card width.</div><div id="metricSpeciesLabels" class="assembly-species-chart"></div></div>
      <div class="card assembly-metric-card"><div class="chart-title">Total contigs</div><div class="chart-subtitle">Number of contigs recovered for each project, seed and K-mer combination.</div><div id="metricTotalContigs" class="assembly-metric-chart"></div></div>
      <div class="card assembly-metric-card"><div class="chart-title">Largest contig</div><div class="chart-subtitle">Largest assembled contig relative to the configured organelle genome range.</div><div id="metricLargestContig" class="assembly-metric-chart"></div></div>
      <div class="card assembly-metric-card"><div class="chart-title">Smallest contig</div><div class="chart-subtitle">Smallest assembled contig relative to the configured organelle genome range.</div><div id="metricSmallestContig" class="assembly-metric-chart"></div></div>
      <div class="card assembly-metric-card"><div class="chart-title">Average organelle coverage</div><div class="chart-subtitle">Average organelle coverage reported by NOVOPlasty.</div><div id="metricAverageCoverage" class="assembly-metric-chart"></div></div>
    </div>

    <div class="card table-card">
      <div class="table-toolbar">
        <div><div class="table-title">Assembly data</div><div id="assemblyTableCount" class="table-count"></div></div>
        <div class="table-tools">
          <div class="table-search-control">
            <span class="filter-label">Search table <span class="info-dot" data-tooltip="Filters Assembly data across project/species, location, seed, K-mer, status and numeric fields. It does not change the plots above.">i</span></span>
            <div class="table-search-wrap">
              <svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path></svg>
              <input id="assemblySearch" type="search" placeholder="Search project, species, location, seed, K-mer or value...">
            </div>
            <div class="assembly-table-help"><svg viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M8 7h8M8 17h8M5 12h14"></path><path d="m8 9-3 3 3 3M16 9l3 3-3 3"></path></svg><span>Hold the right mouse button and drag horizontally to scroll the table.</span></div>
          </div>
        </div>
      </div>
      <div id="assemblyTableScroll" class="table-scroll"><table id="assemblyTable" class="assembly-table resizable-table"><thead><tr id="assemblyTableHead"></tr></thead><tbody id="assemblyTableBody"></tbody></table></div>
    </div>
  </section>

  <section id="pilon" class="section">
    <h2>Pilon polishing <span class="info-dot" data-tooltip="Summarizes Pilon coverage, confirmation and sequence corrections for the filtered runs.">i</span></h2>
    <div class="section-note">Interactive replacements for the static Pilon summary figures.</div>
    <div id="pilonPrimaryGrid" class="chart-grid pilon-grid">
      <div class="card chart-card"><div class="chart-title">Pilon metrics</div><div class="chart-subtitle">Each metric is normalized from 0–100% across the filtered groups; the tooltip preserves the measured value.</div><div id="pilonMetricsHeatmap" class="chart"></div></div>
      <div class="card chart-card"><div class="chart-title">Genome length before and after Pilon</div><div class="chart-subtitle">Median comparison.</div><div id="pilonBeforeAfterChart" class="chart"></div></div>
    </div>
    <div class="card chart-card" style="margin-top:16px"><div class="chart-title">Pilon corrections</div><div class="chart-subtitle">SNPs, insertions and deletions.</div><div id="pilonCorrectionsChart" class="chart"></div></div>
  </section>

  <section id="genome" class="section">
    <h2>Genome structure and tandem-repeat positions <span class="info-dot" data-tooltip="Every filtered rotated assembly is drawn as a separate genomic track. Colored blocks are annotated markers and orange blocks are TRF tandem repeats.">i</span></h2>
    <div class="section-note">Assemblies are grouped by identical Seed + K-mer combinations. Within each group, projects share the same coordinate scale, gene colors and repeat-family colors so differences are easy to compare.</div>
    <div class="card chart-card genome-scroll" style="margin-top:14px"><div id="genomeTimeline" class="chart"></div></div>
  </section>

  <section id="markers" class="section">
    <h2>Marker comparison <span class="info-dot" data-tooltip="Each marker column uses its own minimum-to-maximum color scale so small length differences remain visible.">i</span></h2>
    <div class="section-note">Each marker is an independently scaled heatmap column. A shared relative legend indicates Min and Max for each marker column.</div>
    <div class="card chart-card marker-heatmap-card">
      <div class="chart-title">Marker length heatmap <span class="info-dot" data-tooltip="Choose one marker class at a time. PCGs is selected by default; selecting tRNAs or rRNAs automatically clears the previous selection.">i</span></div>
      <div class="marker-category-controls" aria-label="Marker class">
        <label class="marker-category-option"><input class="marker-category-checkbox" type="checkbox" value="PCGs" checked> PCGs</label>
        <label class="marker-category-option"><input class="marker-category-checkbox" type="checkbox" value="tRNAs"> tRNAs</label>
        <label class="marker-category-option"><input class="marker-category-checkbox" type="checkbox" value="rRNAs"> rRNAs</label>
      </div>
      <div class="chart-subtitle">Only the selected marker class is shown. Each marker column is independently normalized from its own minimum to maximum.</div>
      <div class="marker-heatmap-scroll"><div id="markerLengthHeatmap" class="chart"></div></div>
    </div>
  </section>

  <section id="repeats" class="section">
    <h2>Tandem repeats <span class="info-dot" data-tooltip="Comparative TRF repeat table with proportional in-cell bars, project/species metadata, location, gene context and consensus.">i</span></h2>
    <div id="repeatSubtitle" class="section-note"></div>
    <div class="card table-card">
      <div class="table-toolbar">
        <div><div class="table-title">Comparative repeat table</div><div id="repeatTableCount" class="table-count"></div></div>
        <div class="table-tools">
          <div class="table-search-control">
            <span class="filter-label">Search table <span class="info-dot" data-tooltip="Searches project/species, location, seed, K-mer, repeat metrics, gene context and consensus sequence. It does not change the plots outside this table.">i</span></span>
            <div class="table-search-wrap">
              <svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path></svg>
              <input id="repeatSearch" type="search" placeholder="Search project, species, location, seed, K-mer or repeat value...">
            </div>
            <div class="assembly-table-help"><svg viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M8 7h8M8 17h8M5 12h14"></path><path d="m8 9-3 3 3 3M16 9l3 3-3 3"></path></svg><span>Hold the right mouse button and drag horizontally to scroll the table.</span></div>
          </div>
        </div>
      </div>
      <div id="repeatTableScroll" class="table-scroll"><table id="repeatTable" class="repeat-table assembly-table resizable-table"><thead><tr id="repeatTableHead"></tr></thead><tbody id="repeatTableBody"></tbody></table></div>
    </div>
  </section>

  <section id="snps" class="section">
    <h2>Marker SNPs <span class="info-dot" data-tooltip="Only true SNP positions are shown. Each nucleotide state is drawn directly with D3 from the SNP matrix table.">i</span></h2>
    <div id="snpSubtitle" class="section-note"></div>
    <div id="snpGallery" class="snp-grid"></div>
  </section>

  <section id="map" class="section">
    <h2>Sampling map <span class="info-dot" data-tooltip="Sampling localities are integrated with the current SNP matrices. Choose which markers contribute to the map statistics and optionally display a haplotype network.">i</span></h2>
    <div id="mapSubtitle" class="section-note">Sampling localities are filtered together with Marker SNPs. Hover or click a point to inspect the exact markers carrying differences.</div>
    <div class="map-analysis-panel">
      <div>
        <div class="map-analysis-title">Markers included in the map <span class="info-dot" data-tooltip="Only checked markers contribute to SNP differences, marker counts and the haplotype network. This does not change the Marker SNP cards above.">i</span></div>
        <div class="map-analysis-copy">Use marker selection to ask focused questions, for example whether geographic structure is driven mainly by 12S, 16S or a protein-coding marker.</div>
        <div class="map-marker-actions"><button id="mapSelectAllMarkers" class="map-marker-action" type="button">Select all</button><button id="mapClearMarkers" class="map-marker-action" type="button">Clear</button></div>
        <div id="mapMarkerControls" class="map-marker-options"></div>
      </div>
      <div class="map-network-column">
        <div class="map-analysis-title">Haplotype network <span class="info-dot" data-tooltip="Builds haplotypes from the selected true-SNP marker states. Nodes are unique haplotypes, node size is the number of sequences, and edge labels are SNP distances in a minimum spanning network.">i</span></div>
        <label class="map-network-toggle"><input id="mapHaplotypeToggle" type="checkbox"> Show haplotype network</label>
        <div class="map-network-help">The network is drawn as an inset over the map. H1, H2 and later labels are assigned dynamically from the currently selected projects, filters and markers.</div>
      </div>
    </div>
    <div class="card map-card"><div id="samplingMap"></div><div id="haplotypeNetworkPanel" class="haplotype-network-panel"></div><div id="mapStatus" class="map-note"></div></div>
  </section>

  <footer class="report-footer">
    <div class="footer-brand"><div class="footer-logo">__LOGO_HTML__</div></div>
    <div class="report-footer-grid">
      <div>
        <div class="report-footer-title">moCURA report</div>
        <div class="report-footer-copy">Interactive assembly, polishing, repeat and SNP summary generated from the moCURA workflow.</div>
      </div>
      <div>
        <div class="report-footer-title">Development Team</div>
        <div class="report-footer-copy">Luan Rabelo and Renato Moreira-Oliveira<br>Instituto Tecnológico Vale<br>The project is part of the Brazilian Biodiversity Genomics Consortium, GBB.</div>
      </div>
      <div>
        <div class="report-footer-title">Metadata</div>
        <div class="report-footer-copy">When metadata are provided, species names, localities and sampling coordinates are integrated across the report.</div>
      </div>
    </div>
    <div class="report-footer-credit">Report Web Page is developed by Luan Rabelo.</div>
  </footer>
</div>

<div id="tooltip" class="tooltip"></div>

<script>
const REPORT = __DATA_JSON__;
const REPORT_CONFIG = __CONFIG_JSON__;
const WORLD_BASEMAP = __BASEMAP_JSON__;

const D3_CDNS = [
  'https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js',
  'https://unpkg.com/d3@7.9.0/dist/d3.min.js',
  'https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js'
];
const MAPLIBRE_CDNS = [
  'https://cdn.jsdelivr.net/npm/maplibre-gl@5.13.0/dist/maplibre-gl.js',
  'https://unpkg.com/maplibre-gl@5.13.0/dist/maplibre-gl.js'
];

function showError(message) {
  const box = document.getElementById('errorBox');
  box.style.display = 'block';
  box.textContent = message;
}

function loadExternalScript(url) {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = url;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`Failed to load ${url}`));
    document.head.appendChild(script);
  });
}

async function loadD3() {
  if (window.d3) return;
  const errors = [];
  for (const url of D3_CDNS) {
    try {
      await loadExternalScript(url);
      if (window.d3) return;
    } catch (error) {
      errors.push(error.message);
    }
  }
  throw new Error('D3.js could not be loaded from any configured CDN.\\n' + errors.join('\\n'));
}

async function loadMapLibre() {
  if (window.maplibregl && typeof window.maplibregl.Map === 'function') return true;
  for (const url of MAPLIBRE_CDNS) {
    try {
      await loadExternalScript(url);
      if (window.maplibregl && typeof window.maplibregl.Map === 'function') return true;
    } catch (error) {
      console.warn(error.message);
    }
  }
  return false;
}

const state = {
  projects: new Set(REPORT.projects || []),
  seed: new Set(),
  kmer: new Set(),
  status: new Set(),
  repeats: new Set(),
  assembly: null
};

function allProjectsSelected() {
  return REPORT.projects.length > 0 && state.projects.size === REPORT.projects.length && REPORT.projects.every(project=>state.projects.has(text(project)));
}

function selectedProjectCount() {
  return state.projects.size;
}

function singleSelectedProject() {
  return state.projects.size===1 ? [...state.projects][0] : null;
}

let selectedAssemblyRunKey = null;

const filterOptions = {
  seed: [],
  kmer: [],
  status: ['Circularized','Not circularized'],
  repeats: ['With repeats','Without repeats']
};

const tooltip = document.getElementById('tooltip');
const palette = [
  '#0173B2','#DE8F05','#029E73','#D55E00','#CC78BC',
  '#CA9161','#FBAFE4','#949494','#ECE133','#56B4E9'
];

const snpBaseColors = {
  A: '#4682B4',
  C: '#CD5C5C',
  G: '#87CEEB',
  T: '#8FBC8F',
  '-': '#9CA3AF',
  N: '#E5E7EB'
};

const assemblyColumns = [
  'Project name','Location','Seed Input','K-mer','Circularized','Total contigs','Smallest contig','Largest contig',
  'Average organelle coverage','Pilon Coverage','Pilon Confirmed %',
  'Pilon Corrected snps','Pilon Corrected insertions','Pilon Corrected deletions'
];

const assemblyBarColumns = new Map([
  ['Smallest contig','#56B4E9'],
  ['Largest contig','#0173B2'],
  ['Average organelle coverage','#029E73'],
  ['Pilon Coverage','#DE8F05'],
  ['Pilon Confirmed %','#CC78BC']
]);

const repeatColumns = [
  'Project name','Location','Seed Input','K-mer',
  'Repeat length','Period Size','Copy Number','Consensus Size','Percent Matches','Percent Indels',
  'Gene context label','Consensus'
];

const repeatBarColumns = new Map([
  ['Repeat length','#0173B2'],
  ['Period Size','#56B4E9'],
  ['Copy Number','#029E73'],
  ['Consensus Size','#DE8F05'],
  ['Percent Matches','#CC78BC'],
  ['Percent Indels','#D55E00']
]);

function text(value) { return value === null || value === undefined ? '' : String(value); }
function num(value, fallback = null) { const n = Number(value); return Number.isFinite(n) ? n : fallback; }
function esc(value) { return text(value).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
function unique(rows, col) { return [...new Set(rows.map(r => r[col]).filter(v => v !== null && v !== undefined && text(v) !== ''))].sort((a,b) => text(a).localeCompare(text(b), undefined, {numeric:true})); }
function median(values) { const a = values.map(v => num(v)).filter(v => v !== null).sort((a,b) => a-b); if (!a.length) return null; const m = Math.floor(a.length/2); return a.length%2 ? a[m] : (a[m-1]+a[m])/2; }
function normalizedRunValue(value) {
  const numeric=num(value);
  if(numeric!==null)return String(Number(numeric.toFixed(8)));
  return text(value).trim();
}

function rowKey(row) {
  return `${text(row['Project name']).trim()}\0${text(row['Seed Input']).trim()}\0${normalizedRunValue(row['K-mer'])}`;
}

const summaryByRunKey = new Map(REPORT.summary.map(row => [rowKey(row), row]));
const repeatRunKeys = new Set(REPORT.repeats.map(rowKey));

const metadataByProject = new Map();
[...(REPORT.summary||[]),...(REPORT.genbanks||[]),...(REPORT.markers||[]),...(REPORT.repeats||[]),...(REPORT.metadata_points||[])].forEach(row=>{
  const project=text(row['Project name']).trim();
  if(!project)return;
  const previous=metadataByProject.get(project)||{};
  metadataByProject.set(project,{...previous,...row});
});

let abbreviateSpecies=false;
let markerCategorySelection='PCGs';
const snpReferenceSelection=new Map();
const mapAvailableMarkers=[...new Set((REPORT.snp_matrices||[]).map(matrix=>text(matrix.marker)).filter(Boolean))].sort((a,b)=>a.localeCompare(b,undefined,{numeric:true}));
const mapSelectedMarkers=new Set(mapAvailableMarkers);
let mapShowHaplotypeNetwork=false;

function projectRecord(project) {
  const projectName=text(project).trim();
  const base=REPORT.summary.find(row=>text(row['Project name']).trim()===projectName)
    || REPORT.genbanks.find(row=>text(row['Project name']).trim()===projectName)
    || REPORT.markers.find(row=>text(row['Project name']).trim()===projectName)
    || REPORT.repeats.find(row=>text(row['Project name']).trim()===projectName)
    || {'Project name':projectName};
  return {...base,...(metadataByProject.get(projectName)||{})};
}

function shortSpeciesName(value) {
  const parts=text(value).trim().split(/\s+/).filter(Boolean);
  if(!parts.length)return '';
  if(parts.length===1)return parts[0];
  const genus=abbreviateSpecies?`${parts[0].charAt(0)}.`:parts[0];
  return `${genus} ${parts[1]}`;
}

function projectLabelParts(row) {
  const project=text(row?.['Project name'] ?? row?.project).trim();
  const metadata=metadataByProject.get(project)||{};
  const species=shortSpeciesName(row?.['Species'] ?? row?.species ?? metadata['Species']);
  return {project,species};
}

function projectDisplayText(row) {
  const {project,species}=projectLabelParts(row);
  return species ? `${species} (${project})` : project;
}

function projectDisplayHtml(row) {
  const {project,species}=projectLabelParts(row);
  const projectHtml=esc(project);
  return species ? `<span class="species-label">${esc(species)}</span> <strong>(${projectHtml})</strong>` : `<strong>${projectHtml}</strong>`;
}

function setSvgProjectLabel(selection,row,{prefix='',suffix=''}={}) {
  const {project,species}=projectLabelParts(row);
  selection.text(null);
  if(prefix) selection.append('tspan').attr('font-style','normal').attr('font-weight',400).text(prefix);
  if(species){
    selection.append('tspan').attr('font-style','italic').attr('font-weight',400).text(species);
    selection.append('tspan').attr('font-style','normal').attr('font-weight',750).text(` (${project})`);
  }else{
    selection.append('tspan').attr('font-style','normal').attr('font-weight',750).text(project);
  }
  if(suffix) selection.append('tspan').attr('font-style','normal').attr('font-weight',400).text(suffix);
  return selection;
}

function styleProjectAxisTicks(axisGroup,{rotate90=false}={}) {
  axisGroup.selectAll('.tick text').each(function(project){
    const label=d3.select(this);
    setSvgProjectLabel(label,projectRecord(project));
    if(rotate90){
      label.attr('transform','rotate(-90)').attr('text-anchor','end').attr('dx','-.55em').attr('dy','-.15em');
    }
  });
  return axisGroup;
}

function locationText(row) {
  return text(row['Location'] ?? row.location).trim();
}

function tableColumnLabel(column) {
  if(column==='Project name')return 'Project / Species';
  if(column==='Gene context label')return 'Gene context';
  return column;
}

function formatNumericMetric(column, numeric) {
  if (numeric === null) return '—';
  if (column === 'Smallest contig' || column === 'Largest contig' || column === 'Repeat length' || column === 'Period Size' || column === 'Consensus Size') {
    return `${d3.format(',d')(Math.round(numeric))}${column.includes('contig') ? ' bp' : (column === 'Repeat length' || column === 'Consensus Size' ? ' bp' : '')}`;
  }
  if (column === 'Percent Matches' || column === 'Percent Indels' || column === 'Pilon Confirmed %') {
    return `${d3.format(',.2f')(numeric)}%`;
  }
  if (column.includes('Coverage') || column === 'Average organelle coverage' || column === 'Pilon Coverage') {
    return `${d3.format(',.2f')(numeric)}×`;
  }
  return d3.format(',.2f')(numeric);
}

function rowCircular(row) {
  if (typeof row.Circularized === 'boolean') return row.Circularized;
  const source = summaryByRunKey.get(rowKey(row));
  return source ? source.Circularized === true : false;
}

function rowHasRepeat(row) {
  return repeatRunKeys.has(rowKey(row));
}

function selectionMatches(setValue, candidate) {
  return setValue.has(text(candidate));
}

function matches(row, options={}) {
  if (!state.projects.size || !state.projects.has(text(row['Project name']))) return false;

  if (!options.ignoreSeed) {
    if (!state.seed.size || !selectionMatches(state.seed,row['Seed Input'])) return false;
  }

  if (!options.ignoreKmer) {
    if (!state.kmer.size || !selectionMatches(state.kmer,row['K-mer'])) return false;
  }

  if (!options.ignoreStatus) {
    if (!state.status.size) return false;
    const status = rowCircular(row) ? 'Circularized' : 'Not circularized';
    if (!state.status.has(status)) return false;
  }

  if (!options.ignoreRepeats) {
    if (!state.repeats.size) return false;
    const repeatStatus = rowHasRepeat(row) ? 'With repeats' : 'Without repeats';
    if (!state.repeats.has(repeatStatus)) return false;
  }

  return true;
}

function selectedLabel(selected, options) {
  if (!options.length) return 'No values';
  if (selected.size === options.length) return 'All';
  if (!selected.size) return 'None';
  if (selected.size === 1) return [...selected][0];
  return `${selected.size} selected`;
}

function createMultiSelect(id, values, selected, onChange) {
  const root = document.getElementById(id);
  const options = values.map(text);
  const safeSelected = new Set([...selected].filter(value => options.includes(text(value))));
  if (!safeSelected.size && selected.size) {
    options.forEach(value => safeSelected.add(value));
  }

  root.innerHTML = `
    <button type="button" class="multi-trigger" aria-haspopup="listbox" aria-expanded="false">
      <span class="multi-trigger-label">${esc(selectedLabel(safeSelected,options))}</span>
      <span class="multi-caret">▼</span>
    </button>
    <div class="multi-menu">
      <input class="multi-search" type="search" placeholder="Search...">
      <div class="multi-actions">
        <button type="button" data-action="all">Select all</button>
        <button type="button" data-action="clear">Clear</button>
      </div>
      <div class="multi-options"></div>
    </div>
  `;

  const trigger = root.querySelector('.multi-trigger');
  const search = root.querySelector('.multi-search');
  const optionsBox = root.querySelector('.multi-options');

  function renderOptions(query='') {
    const q = query.trim().toLowerCase();
    const filtered = options.filter(value => value.toLowerCase().includes(q));

    optionsBox.innerHTML = filtered.length
      ? filtered.map(value => `
          <label class="multi-option">
            <input type="checkbox" value="${esc(value)}" ${safeSelected.has(value)?'checked':''}>
            <span>${esc(value)}</span>
          </label>
        `).join('')
      : '<div class="multi-empty">No matching values</div>';

    optionsBox.querySelectorAll('input[type="checkbox"]').forEach(input => {
      input.addEventListener('change', () => {
        if (input.checked) safeSelected.add(input.value);
        else safeSelected.delete(input.value);
        trigger.querySelector('.multi-trigger-label').textContent = selectedLabel(safeSelected,options);
        onChange(new Set(safeSelected));
      });
    });
  }

  trigger.addEventListener('click', event => {
    event.stopPropagation();
    document.querySelectorAll('.multi-select.open').forEach(node => {
      if (node !== root) {
        node.classList.remove('open');
        const otherTrigger = node.querySelector('.multi-trigger');
        if (otherTrigger) otherTrigger.setAttribute('aria-expanded','false');
      }
    });
    root.classList.toggle('open');
    trigger.setAttribute('aria-expanded', root.classList.contains('open') ? 'true' : 'false');
    if (root.classList.contains('open')) setTimeout(() => search.focus(),0);
  });

  search.addEventListener('input', () => renderOptions(search.value));
  search.addEventListener('click', event => event.stopPropagation());

  root.querySelector('[data-action="all"]').addEventListener('click', event => {
    event.stopPropagation();
    safeSelected.clear();
    options.forEach(value => safeSelected.add(value));
    trigger.querySelector('.multi-trigger-label').textContent = selectedLabel(safeSelected,options);
    renderOptions(search.value);
    onChange(new Set(safeSelected));
  });

  root.querySelector('[data-action="clear"]').addEventListener('click', event => {
    event.stopPropagation();
    safeSelected.clear();
    trigger.querySelector('.multi-trigger-label').textContent = selectedLabel(safeSelected,options);
    renderOptions(search.value);
    onChange(new Set(safeSelected));
  });

  root.querySelector('.multi-menu').addEventListener('click', event => event.stopPropagation());
  renderOptions();
}

function closeMultiSelects() {
  document.querySelectorAll('.multi-select.open').forEach(root => {
    root.classList.remove('open');
    const trigger = root.querySelector('.multi-trigger');
    if (trigger) trigger.setAttribute('aria-expanded','false');
  });
}

function chartSize(id, minHeight=410) {
  const el = document.getElementById(id);
  const width = Math.max(360, el.clientWidth || 700);
  return {el, width, height:minHeight};
}

function clearChart(id) { d3.select('#'+id).selectAll('*').remove(); }
function emptyChart(id, message) { clearChart(id); d3.select('#'+id).append('div').attr('class','empty').text(message); }

function hover(event, html) {
  tooltip.innerHTML = html;
  tooltip.style.opacity = 1;
  tooltip.style.left = `${Math.min(window.innerWidth - 330, event.clientX + 14)}px`;
  tooltip.style.top = `${Math.min(window.innerHeight - 140, event.clientY + 14)}px`;
}
function unhover() { tooltip.style.opacity = 0; }

function renderTabs() {
  const allActive=allProjectsSelected();
  const buttons=[`<button class="project-tab all-tab ${allActive?'active':''}" data-project="__ALL__">All data</button>`];
  REPORT.projects.forEach(project=>{
    buttons.push(`<button class="project-tab ${state.projects.has(text(project))?'active':''}" data-project="${esc(project)}">${projectDisplayHtml(projectRecord(project))}</button>`);
  });
  document.getElementById('projectTabs').innerHTML=buttons.join('');

  document.querySelectorAll('#projectTabs [data-project]').forEach(button=>button.addEventListener('click',()=>{
    const project=button.dataset.project;
    if(project==='__ALL__'){
      state.projects=new Set(REPORT.projects.map(text));
    }else if(allProjectsSelected()){
      state.projects=new Set([project]);
    }else if(state.projects.has(project)){
      if(state.projects.size>1)state.projects.delete(project);
    }else{
      state.projects.add(project);
    }

    state.assembly=null;
    document.getElementById('assemblySearch').value='';
    document.getElementById('repeatSearch').value='';
    renderTabs();
    resetFilterSelections();
    renderAll();
  }));
}

function resetFilterSelections() {
  const projectRows=REPORT.summary.filter(row=>state.projects.has(text(row['Project name'])));
  filterOptions.seed=unique(projectRows,'Seed Input').map(text);
  filterOptions.kmer=unique(projectRows,'K-mer').map(text);
  state.seed=new Set(filterOptions.seed);
  state.kmer=new Set(filterOptions.kmer);
  state.status=new Set(filterOptions.status);
  state.repeats=new Set(filterOptions.repeats);
  renderFilterControls();
}

function renderFilterControls() {
  createMultiSelect('seedFilter',filterOptions.seed,state.seed,value=>{state.seed=value;state.assembly=null;renderAll();});
  createMultiSelect('kmerFilter',filterOptions.kmer,state.kmer,value=>{state.kmer=value;state.assembly=null;renderAll();});
  createMultiSelect('statusFilter',filterOptions.status,state.status,value=>{state.status=value;state.assembly=null;renderAll();});
  createMultiSelect('repeatFilter',filterOptions.repeats,state.repeats,value=>{state.repeats=value;state.assembly=null;renderAll();});
}

function summarizeSelection(selected, options, singular, plural) {
  if (selected.size === options.length) return `all ${plural}`;
  if (!selected.size) return `no ${plural}`;
  if (selected.size === 1) return `${singular} ${[...selected][0]}`;
  return `${selected.size} ${plural}`;
}

function updateText() {
  const singleProject=singleSelectedProject();
  const projectSummary=allProjectsSelected() ? 'All projects' : (singleProject ? projectDisplayHtml(projectRecord(singleProject)) : `${selectedProjectCount()} projects selected`);
  document.getElementById('filterSummary').innerHTML=[
    projectSummary,
    summarizeSelection(state.seed,filterOptions.seed,'seed','seeds'),
    summarizeSelection(state.kmer,filterOptions.kmer,'K-mer','K-mers'),
    summarizeSelection(state.status,filterOptions.status,'status','statuses'),
    summarizeSelection(state.repeats,filterOptions.repeats,'repeat filter','repeat states')
  ].join(' · ');

  document.getElementById('assemblySubtitle').innerHTML=singleProject
    ? `Four linked NOVOPlasty metrics for ${projectDisplayHtml(projectRecord(singleProject))}. Hover any point to isolate that same run across every panel.`
    : `Four linked NOVOPlasty metrics comparing ${allProjectsSelected()?'all projects':`${selectedProjectCount()} selected projects`}. Seed Input is color, K-mer is marker shape, and the green interval is the expected genome range.`;

  document.getElementById('repeatSubtitle').innerHTML=singleProject
    ? `Tandem repeats within ${projectDisplayHtml(projectRecord(singleProject))}.`
    : `Tandem repeats comparing ${allProjectsSelected()?'all projects':`${selectedProjectCount()} selected projects`}.`;
}

function updateMetrics() {
  const s = REPORT.summary.filter(matches);
  const g = REPORT.genbanks.filter(matches);
  const r = REPORT.repeats.filter(matches);
  const cov = median(s.map(x => x['Average organelle coverage']));
  document.getElementById('metricProjects').textContent = new Set(s.map(x => x['Project name'])).size;
  document.getElementById('metricAssemblies').textContent = s.length;
  document.getElementById('metricCircularized').textContent = s.filter(x => x.Circularized===true).length;
  document.getElementById('metricGenbanks').textContent = g.length;
  document.getElementById('metricRepeats').textContent = r.length;
  document.getElementById('metricCoverage').textContent = cov===null?'—':`${d3.format('.1f')(cov)}×`;
}

function drawLegend(svg, items, width) {
  const legend = svg.append('g').attr('class','legend').attr('transform','translate(12,14)');
  let x=0, y=0;
  items.forEach((item,i) => {
    const estimated = 18 + text(item).length*6.5;
    if (x + estimated > width - 30) { x=0; y+=18; }
    legend.append('circle').attr('cx',x+5).attr('cy',y+5).attr('r',4).attr('fill',palette[i%palette.length]);
    legend.append('text').attr('x',x+13).attr('y',y+8).text(item);
    x += estimated;
  });
  return y + 25;
}

function seedColor(seed) {
  return (REPORT.style && REPORT.style.seed_colors && REPORT.style.seed_colors[text(seed)]) || palette[0];
}

function markerPath(markerName, size=70) {
  const symbolMap = {
    'circle': d3.symbolCircle,
    'square': d3.symbolSquare,
    'diamond': d3.symbolDiamond,
    'triangle-up': d3.symbolTriangle,
    'triangle-down': d3.symbolTriangle,
    'cross': d3.symbolCross,
    'x': d3.symbolCross,
    'triangle-left': d3.symbolTriangle,
    'triangle-right': d3.symbolTriangle,
    'hexagon': d3.symbolWye
  };
  return d3.symbol().type(symbolMap[markerName] || d3.symbolCircle).size(size)();
}

function markerRotation(markerName) {
  if (markerName === 'triangle-down') return 180;
  if (markerName === 'triangle-left') return -90;
  if (markerName === 'triangle-right') return 90;
  if (markerName === 'x') return 45;
  return 0;
}

function kmerMarker(kmer) {
  return (REPORT.style && REPORT.style.kmer_markers && REPORT.style.kmer_markers[text(kmer)]) || 'circle';
}

function renderAssemblyLegend() {
  const rows = REPORT.summary.filter(matches);
  const seeds = unique(rows,'Seed Input').map(text);
  const kmers = unique(rows,'K-mer').map(text);
  const host = document.getElementById('assemblyLegend');

  if(!rows.length){
    host.innerHTML='<span class="table-count">No assembly data for the current filters.</span>';
    return;
  }

  const seedItems = seeds.map(seed=>`<span class="legend-item"><span class="legend-seed-dot" style="background:${seedColor(seed)}"></span>${esc(seed)}</span>`).join('');
  const kmerItems = kmers.map(kmer=>{
    const marker=kmerMarker(kmer);
    const rotation=markerRotation(marker);
    return `<span class="legend-item"><svg width="16" height="16" viewBox="-8 -8 16 16"><path d="${markerPath(marker,72)}" transform="rotate(${rotation})" fill="#202020"></path></svg>K-mer ${esc(kmer)}</span>`;
  }).join('');

  host.innerHTML = `<span class="legend-item" style="font-weight:700">Seed Input</span>${seedItems}<span class="legend-item" style="font-weight:700;margin-left:4px">K-mer</span>${kmerItems}<span class="legend-item"><span class="legend-range-line"></span>Genome range</span>`;
}

function assemblyRunTooltip(row) {
  return [
    projectDisplayHtml(row),
    `Seed: ${esc(row['Seed Input'])}`,
    `K-mer: ${esc(row['K-mer'])}`,
    `Status: ${rowCircular(row)?'Circularized':'Not circularized'}`,
    `Total contigs: ${esc(row['Total contigs'])}`,
    `Largest contig: ${num(row['Largest contig'])===null?'—':d3.format(',')(num(row['Largest contig']))+' bp'}`,
    `Smallest contig: ${num(row['Smallest contig'])===null?'—':d3.format(',')(num(row['Smallest contig']))+' bp'}`,
    `Average coverage: ${num(row['Average organelle coverage'])===null?'—':d3.format('.2f')(num(row['Average organelle coverage']))+'×'}`
  ].join('<br>');
}

function updateAssemblyInteractionNotice(row=null) {
  const element=document.getElementById('assemblyInteractionStatus');
  if(!element)return;

  if(selectedAssemblyRunKey && row){
    element.innerHTML=`<strong>Isolated:</strong> ${projectDisplayHtml(row)} · ${esc(row['Seed Input'])} · K-mer ${esc(row['K-mer'])}. Click the selected point again to restore all values.`;
  }else{
    element.innerHTML='<strong>Interactive selection:</strong> click any point to isolate that same Project + Seed + K-mer combination across all four plots. Click the selected point again to restore all values.';
  }
}

function applyAssemblySelection() {
  const points=d3.selectAll('.assembly-point');

  if(!selectedAssemblyRunKey){
    points.attr('opacity',1).attr('stroke-width',.7).style('pointer-events','all');
    updateAssemblyInteractionNotice();
    return;
  }

  points
    .attr('opacity',function(){return this.dataset.runKey===selectedAssemblyRunKey?1:0;})
    .attr('stroke-width',function(){return this.dataset.runKey===selectedAssemblyRunKey?1.8:.7;})
    .style('pointer-events',function(){return this.dataset.runKey===selectedAssemblyRunKey?'all':'none';});
}

function highlightAssemblyRun(key, event, row) {
  if(selectedAssemblyRunKey){
    hover(event,assemblyRunTooltip(row));
    return;
  }

  d3.selectAll('.assembly-point').attr('opacity',0.25);
  d3.selectAll('.assembly-point').filter(function(){return this.dataset.runKey===key;}).attr('opacity',1).attr('stroke-width',1.6);
  hover(event,assemblyRunTooltip(row));
}

function clearAssemblyHighlight() {
  if(selectedAssemblyRunKey){
    applyAssemblySelection();
  }else{
    d3.selectAll('.assembly-point').attr('opacity',1).attr('stroke-width',0.7);
  }

  unhover();
}

function toggleAssemblyRun(key, row, event) {
  event.stopPropagation();

  if(selectedAssemblyRunKey===key){
    selectedAssemblyRunKey=null;
    applyAssemblySelection();
    unhover();
    return;
  }

  selectedAssemblyRunKey=key;
  applyAssemblySelection();
  updateAssemblyInteractionNotice(row);
  hover(event,assemblyRunTooltip(row));
}

function kernelEpanechnikov(bandwidth) {
  return value => Math.abs(value /= bandwidth) <= 1 ? 0.75 * (1 - value * value) / bandwidth : 0;
}

function kernelDensityEstimator(kernel, thresholds, values) {
  return thresholds.map(x => [x,d3.mean(values,v=>kernel(x-v)) || 0]);
}

function metricDomain(rows, metric) {
  let values = rows.map(row=>num(row[metric])).filter(value=>value!==null);

  if(metric==='Total contigs'){
    return [0,6.5];
  }

  if(!values.length) return [0,1];

  let [minimum,maximum]=d3.extent(values);
  if(metric==='Largest contig' || metric==='Smallest contig'){
    const rangeStarts=rows.map(row=>num(row['Genome range start'])).filter(value=>value!==null);
    const rangeEnds=rows.map(row=>num(row['Genome range end'])).filter(value=>value!==null);
    if(rangeStarts.length) minimum=Math.min(minimum,d3.min(rangeStarts));
    if(rangeEnds.length) maximum=Math.max(maximum,d3.max(rangeEnds));
  }

  if(minimum===maximum){
    minimum-=Math.max(1,Math.abs(minimum)*0.05);
    maximum+=Math.max(1,Math.abs(maximum)*0.05);
  }

  const pad=(maximum-minimum)*0.07;
  return [Math.max(0,minimum-pad),maximum+pad];
}

function assemblyProjectsForCurrentView() {
  const rows=REPORT.summary.filter(matches);
  return unique(rows,'Project name').map(text);
}

function renderAssemblySpeciesLabels() {
  const projects=assemblyProjectsForCurrentView();
  if(!projects.length) return emptyChart('metricSpeciesLabels','No projects for the selected filters.');

  clearChart('metricSpeciesLabels');
  const container=document.getElementById('metricSpeciesLabels');
  const width=Math.max(240,container.clientWidth||260);
  const rowHeight=52;
  const densityHeight=84;
  const margin={top:densityHeight+18,right:12,bottom:46,left:12};
  const height=Math.max(470,margin.top+projects.length*rowHeight+margin.bottom);
  const rowBackground=(REPORT.style&&REPORT.style.row_background)||'#EEEEEE';
  const svg=d3.select('#metricSpeciesLabels').append('svg').attr('viewBox',`0 0 ${width} ${height}`).attr('width',width).attr('height',height);
  const y=d3.scaleBand().domain(projects).range([margin.top,height-margin.bottom]).paddingInner(.12);

  projects.forEach((project,index)=>{
    if(index%2===0){
      svg.append('rect').attr('x',0).attr('y',y(project)).attr('width',width).attr('height',y.bandwidth()).attr('fill',rowBackground);
    }
    const label=svg.append('text').attr('x',10).attr('y',y(project)+y.bandwidth()/2+4).attr('font-size',10.5).attr('fill','#475569');
    setSvgProjectLabel(label,projectRecord(project));
  });
}

function renderAssemblyMetricChart(id, metric) {
  const allRows=REPORT.summary.filter(matches);
  const rows=allRows.filter(row=>num(row[metric])!==null);
  const projects=assemblyProjectsForCurrentView();
  if(!projects.length || !rows.length) return emptyChart(id,'No data for this metric.');

  clearChart(id);
  const container=document.getElementById(id);
  const width=Math.max(300,container.clientWidth||360);
  const rowHeight=52;
  const densityHeight=84;
  const margin={top:densityHeight+18,right:18,bottom:46,left:24};
  const height=Math.max(470,margin.top+projects.length*rowHeight+margin.bottom);

  const svg=d3.select('#'+id).append('svg').attr('viewBox',`0 0 ${width} ${height}`).attr('width',width).attr('height',height);
  const pointPadding=24;
  const x=d3.scaleLinear().domain(metricDomain(rows,metric)).range([margin.left+pointPadding,width-margin.right-pointPadding]);
  if(metric!=='Total contigs') x.nice(6);
  const y=d3.scaleBand().domain(projects).range([margin.top,height-margin.bottom]).paddingInner(.12);
  const rowBackground=(REPORT.style&&REPORT.style.row_background)||'#EEEEEE';
  const densityFill=(REPORT.style&&REPORT.style.density_fill)||'#E76F51';
  const rangeColor=(REPORT.style&&REPORT.style.genome_range)||'#B0E4CC';

  projects.forEach((project,index)=>{
    if(index%2===0){
      svg.append('rect').attr('x',0).attr('y',y(project)).attr('width',width-margin.right).attr('height',y.bandwidth()).attr('fill',rowBackground);
    }
  });

  if(metric==='Largest contig' || metric==='Smallest contig'){
    const ranges=new Map();
    allRows.forEach(row=>{
      const start=num(row['Genome range start']),end=num(row['Genome range end']);
      if(start!==null&&end!==null)ranges.set(`${start}|${end}`,[start,end]);
    });
    [...ranges.values()].forEach(([start,end])=>{
      svg.append('rect').attr('x',x(start)).attr('y',margin.top).attr('width',Math.max(1,x(end)-x(start))).attr('height',height-margin.top-margin.bottom).attr('fill',rangeColor).attr('fill-opacity',.72).attr('pointer-events','none');
      svg.append('line').attr('x1',x(start)).attr('x2',x(start)).attr('y1',margin.top).attr('y2',height-margin.bottom).attr('stroke',rangeColor).attr('stroke-width',1.6);
      svg.append('line').attr('x1',x(end)).attr('x2',x(end)).attr('y1',margin.top).attr('y2',height-margin.bottom).attr('stroke',rangeColor).attr('stroke-width',1.6);
    });
  }

  const values=rows.map(row=>{
    let value=num(row[metric]);
    if(metric==='Total contigs')value=Math.min(6,value);
    return value;
  }).filter(value=>value!==null);
  const thresholds=x.ticks(60);
  const bandwidth=Math.max((x.domain()[1]-x.domain()[0])/14,metric==='Total contigs'?0.25:1);
  const density=kernelDensityEstimator(kernelEpanechnikov(bandwidth),thresholds,values);
  const densityMax=d3.max(density,d=>d[1])||1;
  const densityScale=d3.scaleLinear().domain([0,densityMax]).range([densityHeight,8]);
  const area=d3.area().x(d=>x(d[0])).y0(densityHeight).y1(d=>densityScale(d[1])).curve(d3.curveBasis);

  svg.append('g').attr('transform',`translate(0,${margin.top-densityHeight-12})`).append('path').datum(density).attr('d',area).attr('fill',densityFill).attr('fill-opacity',.78).attr('stroke',densityFill).attr('stroke-width',1);

  const seeds=unique(allRows,'Seed Input').map(text);
  const seedIndex=new Map(seeds.map((seed,index)=>[seed,index]));
  const kmers=unique(allRows,'K-mer').map(text);
  const kmerIndex=new Map(kmers.map((kmer,index)=>[kmer,index]));

  rows.forEach(row=>{
    let value=num(row[metric]);
    if(metric==='Total contigs')value=Math.min(6,value);
    const project=text(row['Project name']);
    const baseY=y(project)+y.bandwidth()/2;
    const seedOffset=(seedIndex.get(text(row['Seed Input']))-(seeds.length-1)/2)*Math.min(4,18/Math.max(1,seeds.length));
    const kmerOffset=(kmerIndex.get(text(row['K-mer']))-(kmers.length-1)/2)*2.0;
    const pointY=baseY+seedOffset+kmerOffset;
    const marker=kmerMarker(row['K-mer']);
    const rotation=markerRotation(marker);
    const key=rowKey(row);

    svg.append('path').attr('class','assembly-point').attr('data-run-key',key).attr('d',markerPath(marker,82)).attr('transform',`translate(${x(value)},${pointY}) rotate(${rotation})`).attr('fill',seedColor(row['Seed Input'])).attr('stroke','#202020').attr('stroke-width',.7).style('cursor','pointer').on('mouseenter',(event)=>highlightAssemblyRun(key,event,row)).on('mousemove',(event)=>hover(event,assemblyRunTooltip(row))).on('mouseleave',clearAssemblyHighlight).on('click',(event)=>toggleAssemblyRun(key,row,event));
  });

  const xAxis=d3.axisBottom(x).ticks(metric==='Total contigs'?7:5);
  if(metric==='Total contigs'){
    xAxis.tickValues([0,1,2,3,4,5,6]).tickFormat(value=>value===6?'>5':value);
  }else{
    xAxis.tickFormat(value=>Math.abs(value)>=1000?d3.format('~s')(value):value);
  }

  svg.append('g').attr('class','axis').attr('transform',`translate(0,${height-margin.bottom})`).call(xAxis);
  svg.append('g').attr('class','axis').attr('transform',`translate(${margin.left},0)`).call(d3.axisLeft(y).tickFormat(()=>'' ));

  if(metric==='Average organelle coverage'){
    svg.append('text').attr('x',(margin.left+width-margin.right)/2).attr('y',height-8).attr('text-anchor','middle').attr('font-size',10).attr('fill','#64748b').text('Coverage (×)');
  }else if(metric!=='Total contigs'){
    svg.append('text').attr('x',(margin.left+width-margin.right)/2).attr('y',height-8).attr('text-anchor','middle').attr('font-size',10).attr('fill','#64748b').text('Base pairs');
  }
}

function renderAssemblyOverview() {
  const visibleKeys=new Set(REPORT.summary.filter(matches).map(rowKey));
  if(selectedAssemblyRunKey && !visibleKeys.has(selectedAssemblyRunKey))selectedAssemblyRunKey=null;
  renderAssemblyLegend();
  renderAssemblySpeciesLabels();
  renderAssemblyMetricChart('metricTotalContigs','Total contigs');
  renderAssemblyMetricChart('metricLargestContig','Largest contig');
  renderAssemblyMetricChart('metricSmallestContig','Smallest contig');
  renderAssemblyMetricChart('metricAverageCoverage','Average organelle coverage');
  applyAssemblySelection();
}


function renderHeatmap(id, rows, xCol, yCol, valueCol, xLabel, valueSuffix='') {
  const clean=rows.filter(row=>num(row[valueCol])!==null);

  if(!clean.length){
    return emptyChart(id,'No data for this heatmap.');
  }

  clearChart(id);

  const {width,height}=chartSize(id);
  const margin={top:28,right:26,bottom:xCol==='Project name'?165:112,left:yCol==='Project name'?190:112};
  const xValues=unique(clean,xCol);
  const yValues=unique(clean,yCol);
  const cells=[];

  xValues.forEach(xValue=>{
    yValues.forEach(yValue=>{
      const values=clean
        .filter(row=>text(row[xCol])===text(xValue)&&text(row[yCol])===text(yValue))
        .map(row=>row[valueCol]);

      const value=median(values);

      if(value!==null){
        cells.push({x:xValue,y:yValue,value});
      }
    });
  });

  const svg=d3.select('#'+id).append('svg').attr('viewBox',`0 0 ${width} ${height}`);
  const x=d3.scaleBand().domain(xValues.map(text)).range([margin.left,width-margin.right]).padding(.04);
  const y=d3.scaleBand().domain(yValues.map(text)).range([margin.top,height-margin.bottom]).padding(.04);
  const extent=d3.extent(cells,cell=>cell.value);
  const domain=extent[0]===extent[1]?[extent[0]-1,extent[1]+1]:extent;
  const color=d3.scaleSequential(d3.interpolateCividis).domain(domain);

  svg.append('g')
    .selectAll('rect')
    .data(cells)
    .join('rect')
    .attr('x',cell=>x(text(cell.x)))
    .attr('y',cell=>y(text(cell.y)))
    .attr('width',x.bandwidth())
    .attr('height',y.bandwidth())
    .attr('fill',cell=>color(cell.value))
    .on('mousemove',(event,cell)=>{ const xLabelHtml=xCol==='Project name'?projectDisplayHtml(projectRecord(cell.x)):`<strong>${esc(cell.x)}</strong>`; const yLabelHtml=yCol==='Project name'?projectDisplayHtml(projectRecord(cell.y)):esc(cell.y); hover(event,`${xLabelHtml}<br>${yLabelHtml}<br>${d3.format(',.2f')(cell.value)}${valueSuffix}`); })
    .on('mouseleave',unhover);

  const xAxisGroup=svg.append('g')
    .attr('class','axis')
    .attr('transform',`translate(0,${height-margin.bottom})`)
    .call(d3.axisBottom(x));
  if(xCol!=='Project name') xAxisGroup.selectAll('text').attr('transform','rotate(-45)').style('text-anchor','end');
  if(xCol==='Project name') styleProjectAxisTicks(xAxisGroup,{rotate90:true});

  const heatmapYAxis=svg.append('g')
    .attr('class','axis')
    .attr('transform',`translate(${margin.left},0)`)
    .call(d3.axisLeft(y));
  if(yCol==='Project name') styleProjectAxisTicks(heatmapYAxis);

  svg.append('text')
    .attr('x',(margin.left+width-margin.right)/2)
    .attr('y',height-8)
    .attr('text-anchor','middle')
    .attr('font-size',11)
    .attr('fill','#64748b')
    .text(xLabel);
}

function groupMedian(rows, groupCol, valueCol) {
  const map=new Map();
  rows.forEach(r=>{const g=text(r[groupCol]),v=num(r[valueCol]);if(!g||v===null)return;if(!map.has(g))map.set(g,[]);map.get(g).push(v);});
  return new Map([...map.entries()].map(([g,v])=>[g,median(v)]));
}

function updatePilonLayout() {
  const rows=REPORT.summary.filter(matches);
  const projectCount=new Set(rows.map(row=>text(row['Project name']))).size;
  const seedCount=new Set(rows.map(row=>text(row['Seed Input']))).size;
  const groupCount=singleSelectedProject()?Math.max(seedCount,new Set(rows.map(row=>text(row['K-mer']))).size):projectCount;
  const grid=document.getElementById('pilonPrimaryGrid');
  const stackThreshold=Math.max(1,num(REPORT_CONFIG.pilon_stack_threshold,10));
  if(grid)grid.classList.toggle('stacked',groupCount>stackThreshold || window.innerWidth<1180);

  const maxHeight=Math.max(520,num(REPORT_CONFIG.pilon_max_height,900));
  const heightPerGroup=Math.max(8,num(REPORT_CONFIG.pilon_height_per_group,22));
  const dynamicHeight=Math.min(maxHeight,Math.max(410,350+Math.max(0,groupCount-8)*heightPerGroup));
  ['pilonMetricsHeatmap','pilonBeforeAfterChart','pilonCorrectionsChart'].forEach(id=>{
    const element=document.getElementById(id);
    if(element)element.style.minHeight=`${dynamicHeight}px`;
  });
}

function renderPilonMetrics() {
  const rows=REPORT.summary.filter(matches);
  const groupCol=singleSelectedProject() ? 'Seed Input' : 'Project name';
  const groups=unique(rows,groupCol);
  const metrics=['Pilon Coverage','Pilon Confirmed %','Pilon Corrected snps','Pilon Corrected insertions','Pilon Corrected deletions'];

  if(!groups.length){
    return emptyChart('pilonMetricsHeatmap','No Pilon data.');
  }

  clearChart('pilonMetricsHeatmap');

  const {width,height}=chartSize('pilonMetricsHeatmap');
  const margin={top:25,right:82,bottom:groupCol==='Project name'?165:110,left:150};
  const svg=d3.select('#pilonMetricsHeatmap').append('svg').attr('viewBox',`0 0 ${width} ${height}`);
  const x=d3.scaleBand().domain(groups.map(text)).range([margin.left,width-margin.right]).padding(.04);
  const y=d3.scaleBand().domain(metrics).range([margin.top,height-margin.bottom]).padding(.04);
  const cells=[];

  metrics.forEach(metric=>{
    const med=groupMedian(rows,groupCol,metric);
    const values=[...med.values()];
    const extent=d3.extent(values);

    groups.forEach(group=>{
      const actual=med.get(text(group));

      if(actual===undefined){
        return;
      }

      const normalized=extent[0]===extent[1]?50:100*(actual-extent[0])/(extent[1]-extent[0]);
      cells.push({group,metric,actual,norm:normalized});
    });
  });

  const color=d3.scaleSequential(d3.interpolateGnBu).domain([0,100]);

  svg.append('g')
    .selectAll('rect')
    .data(cells)
    .join('rect')
    .attr('x',cell=>x(text(cell.group)))
    .attr('y',cell=>y(cell.metric))
    .attr('width',x.bandwidth())
    .attr('height',y.bandwidth())
    .attr('fill',cell=>color(cell.norm))
    .on('mousemove',(event,cell)=>hover(event,`${groupCol==='Project name'?projectDisplayHtml(projectRecord(cell.group)):`<strong>${esc(cell.group)}</strong>`}<br>${esc(cell.metric)}: ${d3.format(',.2f')(cell.actual)}<br>Relative scale: ${d3.format('.0f')(cell.norm)}%`))
    .on('mouseleave',unhover);

  const pilonXAxis=svg.append('g')
    .attr('class','axis')
    .attr('transform',`translate(0,${height-margin.bottom})`)
    .call(d3.axisBottom(x));
  if(groupCol!=='Project name') pilonXAxis.selectAll('text').attr('transform','rotate(-45)').style('text-anchor','end');
  if(groupCol==='Project name') styleProjectAxisTicks(pilonXAxis,{rotate90:true});

  svg.append('g')
    .attr('class','axis')
    .attr('transform',`translate(${margin.left},0)`)
    .call(d3.axisLeft(y));

  const legendHeight=Math.max(120,height-margin.top-margin.bottom);
  const legendWidth=14;
  const legendX=width-margin.right+24;
  const legendY=margin.top;
  const legendScale=d3.scaleLinear().domain([0,100]).range([legendHeight,0]);
  const gradientId='pilonMetricsGradient';

  const defs=svg.append('defs');
  const gradient=defs.append('linearGradient').attr('id',gradientId).attr('x1','0%').attr('x2','0%').attr('y1','100%').attr('y2','0%');

  d3.range(0,101,10).forEach(value=>{
    gradient.append('stop').attr('offset',`${value}%`).attr('stop-color',color(value));
  });

  svg.append('rect')
    .attr('x',legendX)
    .attr('y',legendY)
    .attr('width',legendWidth)
    .attr('height',legendHeight)
    .attr('fill',`url(#${gradientId})`)
    .attr('stroke','#cbd5e1')
    .attr('stroke-width',.7);

  svg.append('g')
    .attr('class','axis')
    .attr('transform',`translate(${legendX+legendWidth},${legendY})`)
    .call(d3.axisRight(legendScale).tickValues([0,25,50,75,100]).tickFormat(value=>`${value}%`));

  svg.append('text')
    .attr('x',legendX+legendWidth/2)
    .attr('y',legendY-9)
    .attr('text-anchor','middle')
    .attr('font-size',9)
    .attr('font-weight',650)
    .attr('fill','#64748b')
    .text('Relative');
}

function renderGroupedBars(id, groups, series, yLabel, projectGroups=false) {
  if(!groups.length) return emptyChart(id,'No data.');
  clearChart(id);
  const {width,height}=chartSize(id);
  const margin={top:38,right:20,bottom:projectGroups?155:90,left:66};
  const svg=d3.select('#'+id).append('svg').attr('viewBox',`0 0 ${width} ${height}`);
  const x0=d3.scaleBand().domain(groups.map(text)).range([margin.left,width-margin.right]).padding(.18);
  const x1=d3.scaleBand().domain(series.map(s=>s.name)).range([0,x0.bandwidth()]).padding(.08);
  const max=d3.max(series,s=>d3.max(s.values,v=>v||0))||1;
  const y=d3.scaleLinear().domain([0,max]).nice().range([height-margin.bottom,margin.top]);
  drawLegend(svg,series.map(s=>s.name),width);
  series.forEach((s,si)=>{
    svg.append('g').selectAll('rect').data(groups.map((g,i)=>({group:g,value:s.values[i]}))).join('rect')
      .attr('x',d=>x0(text(d.group))+x1(s.name)).attr('y',d=>y(d.value||0)).attr('width',x1.bandwidth()).attr('height',d=>y(0)-y(d.value||0)).attr('fill',palette[si%palette.length])
      .on('mousemove',(event,d)=>hover(event,`${projectGroups?projectDisplayHtml(projectRecord(d.group)):`<strong>${esc(d.group)}</strong>`}<br>${esc(s.name)}: ${d3.format(',.2f')(d.value||0)}`)).on('mouseleave',unhover);
  });
  const groupedXAxis=svg.append('g').attr('class','axis').attr('transform',`translate(0,${height-margin.bottom})`).call(d3.axisBottom(x0));
  if(!projectGroups) groupedXAxis.selectAll('text').attr('transform',groups.length>7?'rotate(-45)':null).style('text-anchor',groups.length>7?'end':'middle');
  if(projectGroups) styleProjectAxisTicks(groupedXAxis,{rotate90:true});
  svg.append('g').attr('class','axis').attr('transform',`translate(${margin.left},0)`).call(d3.axisLeft(y).ticks(6));
  svg.append('text').attr('transform','rotate(-90)').attr('x',-(height/2)).attr('y',14).attr('text-anchor','middle').attr('font-size',11).attr('fill','#64748b').text(yLabel);
}

function renderPilonBeforeAfter() {
  const rows=REPORT.summary.filter(matches), groupCol=singleSelectedProject()?'Seed Input':'Project name', groups=unique(rows,groupCol);
  const before=groupMedian(rows,groupCol,'Largest contig'), after=groupMedian(rows,groupCol,'Pilon Total bases');
  renderGroupedBars('pilonBeforeAfterChart',groups,[{name:'Before Pilon',values:groups.map(g=>before.get(text(g))??0)},{name:'After Pilon',values:groups.map(g=>after.get(text(g))??0)}],'Genome length (bp)',!singleSelectedProject());
}

function renderPilonCorrections() {
  const rows=REPORT.summary.filter(matches), groupCol=singleSelectedProject()?'K-mer':'Project name', groups=unique(rows,groupCol);
  const cols=[['Pilon Corrected snps','SNPs'],['Pilon Corrected insertions','Insertions'],['Pilon Corrected deletions','Deletions']];
  const series=cols.map(([col,name])=>{const med=groupMedian(rows,groupCol,col);return {name,values:groups.map(g=>med.get(text(g))??0)}});
  renderGroupedBars('pilonCorrectionsChart',groups.map(g=>singleSelectedProject()?`K ${g}`:g),series,'Median corrections',!singleSelectedProject());
}

function renderAssemblyTable() {
  const q=document.getElementById('assemblySearch').value.trim().toLowerCase();
  const rows=REPORT.summary
    .filter(matches)
    .filter(row=>!q||assemblyColumns.some(column=>text(row[column]).toLowerCase().includes(q))||projectDisplayText(row).toLowerCase().includes(q))
    .slice()
    .sort((a,b)=>{
      const project=text(a['Project name']).localeCompare(text(b['Project name']),undefined,{numeric:true});
      if(project)return project;
      const seed=text(a['Seed Input']).localeCompare(text(b['Seed Input']),undefined,{numeric:true});
      if(seed)return seed;
      return num(a['K-mer'],0)-num(b['K-mer'],0);
    });

  const maxima=new Map();
  assemblyBarColumns.forEach((color,column)=>{
    maxima.set(column,d3.max(rows,row=>num(row[column],0))||0);
  });

  document.getElementById('assemblyTableCount').textContent=`${rows.length} run${rows.length===1?'':'s'} shown`;
  document.getElementById('assemblyTableHead').innerHTML=assemblyColumns.map((column,index)=>`<th class="${index<2?'sticky-col':''}">${esc(tableColumnLabel(column))}</th>`).join('');

  let previousProject=null;

  document.getElementById('assemblyTableBody').innerHTML=rows.map(row=>{
    const project=text(row['Project name']);
    const projectStart=previousProject!==null&&project!==previousProject;
    previousProject=project;

    const cells=assemblyColumns.map(column=>{
      const value=row[column];

      if(column==='Circularized'){
        const yes=value===true;
        return `<td class="circularized-cell ${yes?'yes':'no'}"><span>${yes?'Yes':'No'}</span></td>`;
      }

      if(column==='Project name'){
        return `<td class="sticky-col">${projectDisplayHtml(projectRecord(row['Project name']))}</td>`;
      }

      if(assemblyBarColumns.has(column)){
        const numeric=num(value);
        const maximum=maxima.get(column)||0;
        const percentage=numeric===null||maximum<=0?0:Math.max(0,Math.min(100,100*numeric/maximum));
        const formatted=formatNumericMetric(column,numeric);
        return `<td class="data-bar-cell" style="--bar-width:${percentage.toFixed(2)}%;--bar-color:${assemblyBarColumns.get(column)}38"><div class="cell-bar"></div><span class="cell-value">${formatted}</span></td>`;
      }

      if(typeof value==='number'){
        if(column==='K-mer'||column==='Total contigs'||column.startsWith('Pilon Corrected')){
          return `<td>${d3.format(',')(value)}</td>`;
        }
        return `<td>${formatNumericMetric(column,value)}</td>`;
      }

      return `<td class="${column==='Location'?'sticky-col':''}">${esc(value)}</td>`;
    }).join('');

    return `<tr class="${projectStart?'project-start':''}">${cells}</tr>`;
  }).join('');

  initResizableTable(document.getElementById('assemblyTable'),assemblyColumns);
}

function assemblyOptions() {
  const rows=REPORT.genbanks.filter(matches), map=new Map();
  rows.forEach(r=>map.set(r['Assembly key'],r));
  return [...map.entries()].sort((a,b)=>a[0].localeCompare(b[0],undefined,{numeric:true}));
}

function refreshAssemblySelect() {
  const opts=assemblyOptions();
  if(!opts.length){state.assembly=null;return;}
  if(!state.assembly||!opts.some(([k])=>k===state.assembly))state.assembly=opts[0][0];
}

function renderGenomeTimeline() {
  const genomes=REPORT.genbanks.filter(matches).sort((a,b)=>{
    const seed=text(a['Seed Input']).localeCompare(text(b['Seed Input']),undefined,{numeric:true});
    if(seed)return seed;
    const kmer=num(a['K-mer'],0)-num(b['K-mer'],0);
    if(kmer)return kmer;
    const project=text(a['Project name']).localeCompare(text(b['Project name']),undefined,{numeric:true});
    if(project)return project;
    return num(a['Assembly copy'],0)-num(b['Assembly copy'],0);
  });

  if(!genomes.length){
    return emptyChart('genomeTimeline','No rotated circularized assemblies for these filters.');
  }

  clearChart('genomeTimeline');

  const markers=REPORT.markers.filter(matches).filter(row=>num(row.Start)!==null&&num(row.End)!==null);
  const repeats=REPORT.repeats.filter(matches).filter(row=>num(row.Start)!==null&&num(row.End)!==null);
  const markersByAssembly=d3.group(markers,row=>row['Assembly key']);
  const repeatsByAssembly=d3.group(repeats,row=>row['Assembly key']);

  const markerColor=d3.scaleOrdinal(unique(markers,'Marker').map(text),palette);
  const repeatColor=d3.scaleOrdinal(unique(repeats,'Repeat family label').map(text),palette.slice().reverse());

  const groups=d3.groups(genomes,genome=>`${text(genome['Seed Input'])}\0${normalizedRunValue(genome['K-mer'])}`)
    .map(([key,assemblies])=>({
      key,
      seed:text(assemblies[0]['Seed Input']),
      kmer:normalizedRunValue(assemblies[0]['K-mer']),
      assemblies
    }));

  const container=document.getElementById('genomeTimeline');
  const width=Math.max(760,container.clientWidth||1100);
  const labelWidth=395;
  const plotLeft=labelWidth+48;
  const plotRight=28;
  const headerHeight=58;
  const rowHeight=92;
  const groupGap=22;
  const topMargin=14;
  const bottomMargin=24;
  const totalHeight=topMargin+groups.reduce((sum,group)=>sum+headerHeight+group.assemblies.length*rowHeight+groupGap,0)+bottomMargin;

  const svg=d3.select('#genomeTimeline')
    .append('svg')
    .attr('width',width)
    .attr('height',totalHeight)
    .attr('viewBox',`0 0 ${width} ${totalHeight}`);

  let groupY=topMargin;

  groups.forEach(group=>{
    const groupAssemblies=group.assemblies;
    const groupAssemblyKeys=new Set(groupAssemblies.map(row=>row['Assembly key']));
    const groupMarkers=markers.filter(row=>groupAssemblyKeys.has(row['Assembly key']));
    const groupRepeats=repeats.filter(row=>groupAssemblyKeys.has(row['Assembly key']));

    const maximumLength=d3.max(groupAssemblies,genome=>{
      const assemblyMarkers=markersByAssembly.get(genome['Assembly key'])||[];
      const assemblyRepeats=repeatsByAssembly.get(genome['Assembly key'])||[];
      return Math.max(
        num(genome['Record length'],0),
        d3.max(assemblyMarkers,row=>num(row.End,0))||0,
        d3.max(assemblyRepeats,row=>num(row.End,0))||0
      );
    })||1;

    const x=d3.scaleLinear().domain([1,maximumLength]).range([plotLeft,width-plotRight]);

    svg.append('rect')
      .attr('x',0)
      .attr('y',groupY)
      .attr('width',width)
      .attr('height',headerHeight-8)
      .attr('rx',8)
      .attr('fill','#eef4f7');

    svg.append('text')
      .attr('x',14)
      .attr('y',groupY+19)
      .attr('font-size',12)
      .attr('font-weight',750)
      .attr('fill','#0f172a')
      .text(`Seed ${group.seed} · K-mer ${group.kmer}`);

    svg.append('text')
      .attr('x',14)
      .attr('y',groupY+37)
      .attr('font-size',10)
      .attr('fill','#64748b')
      .text(`${groupAssemblies.length} assembl${groupAssemblies.length===1?'y':'ies'} · ${new Set(groupMarkers.map(row=>text(row.Marker))).size} marker types · ${groupRepeats.length} TRF repeat records`);

    svg.append('g')
      .attr('class','axis')
      .attr('transform',`translate(0,${groupY+48})`)
      .call(d3.axisTop(x).ticks(8).tickFormat(value=>d3.format(',')(value)));

    const rowsStart=groupY+headerHeight;

    groupAssemblies.forEach((genome,index)=>{
      const y0=rowsStart+index*rowHeight;
      const assemblyMarkers=(markersByAssembly.get(genome['Assembly key'])||[]).slice().sort((a,b)=>num(a.Start,0)-num(b.Start,0));
      const assemblyRepeats=(repeatsByAssembly.get(genome['Assembly key'])||[]).slice().sort((a,b)=>num(a.Start,0)-num(b.Start,0));
      const genomeLength=Math.max(
        num(genome['Record length'],0),
        d3.max(assemblyMarkers,row=>num(row.End,0))||0,
        d3.max(assemblyRepeats,row=>num(row.End,0))||0
      );

      if(index%2===0){
        svg.append('rect')
          .attr('x',0)
          .attr('y',y0)
          .attr('width',width)
          .attr('height',rowHeight-2)
          .attr('fill','#fafafa');
      }

      if(index>0){
        svg.append('line')
          .attr('x1',0)
          .attr('x2',width)
          .attr('y1',y0)
          .attr('y2',y0)
          .attr('stroke','#e2e8f0');
      }

      const genomeProjectLabel=svg.append('text')
        .attr('x',14)
        .attr('y',y0+22)
        .attr('font-size',10.5)
        .attr('fill','#0f172a');
      setSvgProjectLabel(genomeProjectLabel,genome);

      svg.append('text')
        .attr('x',14)
        .attr('y',y0+39)
        .attr('font-size',9.5)
        .attr('fill','#64748b')
        .text(`copy ${genome['Assembly copy']} · ${d3.format(',')(genomeLength)} bp${locationText(genome)?` · ${locationText(genome)}`:''}`);

      const repeatSummary=assemblyRepeats.map((repeat,index)=>`Repeat ${index+1}: Repeat length ${text(repeat['Repeat length'])} bp · Consensus size ${text(repeat['Consensus Size'])} bp · Copy number ${text(repeat['Copy Number'])}`).join(' | ');
      svg.append('text')
        .attr('x',14)
        .attr('y',y0+56)
        .attr('font-size',9.5)
        .attr('font-weight',650)
        .attr('fill','#475569')
        .text(`${assemblyRepeats.length} repeat${assemblyRepeats.length===1?'':'s'}`);
      svg.append('text')
        .attr('x',14)
        .attr('y',y0+72)
        .attr('font-size',8.3)
        .attr('fill','#64748b')
        .text(repeatSummary || 'No tandem repeats');

      const plusY=y0+20;
      const minusY=y0+40;
      const repeatY=y0+64;

      [
        {label:'+',y:plusY},
        {label:'−',y:minusY},
        {label:'TRF',y:repeatY}
      ].forEach(track=>{
        svg.append('line')
          .attr('x1',plotLeft)
          .attr('x2',x(genomeLength))
          .attr('y1',track.y)
          .attr('y2',track.y)
          .attr('stroke','#cbd5e1');

        svg.append('text')
          .attr('x',plotLeft-8)
          .attr('y',track.y+3.5)
          .attr('text-anchor','end')
          .attr('font-size',8.5)
          .attr('font-weight',700)
          .attr('fill','#94a3b8')
          .text(track.label);
      });

      assemblyMarkers.forEach(marker=>{
        const strand=text(marker.Strand)==='-'?'-':'+';
        const trackY=strand==='-'?minusY:plusY;

        svg.append('rect')
          .attr('x',x(num(marker.Start)))
          .attr('y',trackY-6)
          .attr('width',Math.max(2,x(num(marker.End))-x(num(marker.Start))))
          .attr('height',12)
          .attr('rx',2)
          .attr('fill',markerColor(marker.Marker))
          .attr('stroke','#ffffff')
          .attr('stroke-width',.5)
          .on('mousemove',event=>hover(event,`<b>${esc(marker.Marker)}</b><br>${projectDisplayHtml(genome)}${locationText(genome)?`<br>Location: ${esc(locationText(genome))}`:''}<br>Seed ${esc(group.seed)} · K-mer ${esc(group.kmer)}<br>${esc(marker.Start)}–${esc(marker.End)} bp<br>Strand: ${esc(strand)}`))
          .on('mouseleave',unhover);
      });

      assemblyRepeats.forEach(repeat=>{
        const family=text(repeat['Repeat family label'])||text(repeat.Consensus)||'Repeat';
        const repeatStart=x(num(repeat.Start));
        const repeatEnd=x(num(repeat.End));
        const repeatWidth=Math.max(3,repeatEnd-repeatStart);

        svg.append('rect')
          .attr('x',repeatStart)
          .attr('y',repeatY-6)
          .attr('width',repeatWidth)
          .attr('height',12)
          .attr('rx',2)
          .attr('fill',repeatColor(family))
          .attr('stroke','#ffffff')
          .attr('stroke-width',.5)
          .on('mousemove',event=>hover(event,`<b>${esc(family)}</b><br>${projectDisplayHtml(genome)}${locationText(genome)?`<br>Location: ${esc(locationText(genome))}`:''}<br>Seed ${esc(group.seed)} · K-mer ${esc(group.kmer)}<br>${esc(repeat.Start)}–${esc(repeat.End)} bp<br>Repeat length: ${esc(repeat['Repeat length'])}<br>Consensus size: ${esc(repeat['Consensus Size'])}<br>Copies: ${esc(repeat['Copy Number'])}<br>${esc(repeat['Gene context'])}`))
          .on('mouseleave',unhover);

      });
    });

    groupY=rowsStart+groupAssemblies.length*rowHeight+groupGap;
  });
}

function markerCategory(markerName) {
  const raw=text(markerName).trim();
  const normalized=raw.toUpperCase().replace(/[^A-Z0-9]/g,'');
  if(/^TRNA/.test(normalized)||/^TRN[A-Z]/.test(normalized)||raw.toLowerCase().startsWith('trna'))return 'tRNAs';
  if(['12S','16S','RRNS','RRNL','12SRRNA','16SRRNA'].includes(normalized)||normalized.includes('RRNA'))return 'rRNAs';
  const pcgs=new Set(['ATP6','ATP8','COI','COII','COIII','CO1','CO2','CO3','COX1','COX2','COX3','CYTB','COB','ND1','ND2','ND3','ND4','ND4L','ND5','ND6','NAD1','NAD2','NAD3','NAD4','NAD4L','NAD5','NAD6']);
  return pcgs.has(normalized)?'PCGs':'Other';
}

function initMarkerCategoryControls() {
  document.querySelectorAll('.marker-category-checkbox').forEach(input=>{
    input.checked=input.value===markerCategorySelection;
    input.addEventListener('change',()=>{
      if(!input.checked){ input.checked=true; return; }
      markerCategorySelection=input.value;
      document.querySelectorAll('.marker-category-checkbox').forEach(other=>{ other.checked=other===input; });
      renderMarkerHeatmap();
    });
  });
}

function renderMarkerHeatmap() {
  const rows=REPORT.markers.filter(matches).filter(row=>num(row['Marker length'])!==null).filter(row=>markerCategory(row.Marker)===markerCategorySelection);
  if(!rows.length) return emptyChart('markerLengthHeatmap',`No ${markerCategorySelection} marker-length data for the selected filters.`);

  clearChart('markerLengthHeatmap');

  const markers=unique(rows,'Marker').map(text);
  const rowMap=new Map();
  rows.forEach(row=>{
    const key=rowKey(row);
    if(!rowMap.has(key)) rowMap.set(key,{key,row,values:new Map()});
    rowMap.get(key).values.set(text(row.Marker),num(row['Marker length']));
  });

  const displayRows=[...rowMap.values()].sort((a,b)=>{
    const project=projectDisplayText(a.row).localeCompare(projectDisplayText(b.row),undefined,{numeric:true});
    if(project)return project;
    const location=locationText(a.row).localeCompare(locationText(b.row),undefined,{numeric:true});
    if(location)return location;
    const seed=text(a.row['Seed Input']).localeCompare(text(b.row['Seed Input']),undefined,{numeric:true});
    if(seed)return seed;
    return num(a.row['K-mer'],0)-num(b.row['K-mer'],0);
  });

  const container=document.getElementById('markerLengthHeatmap');
  const cellWidth=72;
  const labelWidth=320;
  const legendWidth=72;
  const topSpace=20;
  const rowHeight=30;
  const bottomSpace=72;
  const width=Math.max(container.clientWidth||980,labelWidth+markers.length*cellWidth+legendWidth+28);
  const height=Math.max(330,topSpace+displayRows.length*rowHeight+bottomSpace);
  const svg=d3.select('#markerLengthHeatmap').append('svg').attr('width',width).attr('height',height).attr('viewBox',`0 0 ${width} ${height}`);
  const x=d3.scaleBand().domain(markers).range([labelWidth,width-legendWidth-18]).paddingInner(.08);
  const y=d3.scaleBand().domain(displayRows.map(item=>item.key)).range([topSpace,height-bottomSpace]).paddingInner(.05);
  const markerStats=new Map();
  markers.forEach(marker=>{
    const values=displayRows.map(item=>item.values.get(marker)).filter(value=>value!==undefined&&value!==null);
    markerStats.set(marker,{minimum:d3.min(values),maximum:d3.max(values)});
  });

  const matrixTop=topSpace;
  const matrixBottom=height-bottomSpace;
  const legendX=width-legendWidth+14;
  const legendHeight=Math.max(80,matrixBottom-matrixTop);
  const legendY=matrixTop;
  const defs=svg.append('defs');
  const gradient=defs.append('linearGradient').attr('id','markerRelativeGradientVertical').attr('x1','0%').attr('x2','0%').attr('y1','100%').attr('y2','0%');
  d3.range(0,101,10).forEach(value=>gradient.append('stop').attr('offset',`${value}%`).attr('stop-color',d3.interpolateCividis(value/100)));

  displayRows.forEach((item,index)=>{
    if(index%2===0) svg.append('rect').attr('x',0).attr('y',y(item.key)).attr('width',width).attr('height',y.bandwidth()).attr('fill','#f8fafc');
    if(index>0 && text(item.row['Project name'])!==text(displayRows[index-1].row['Project name'])) svg.append('line').attr('x1',0).attr('x2',width).attr('y1',y(item.key)-3).attr('y2',y(item.key)-3).attr('stroke','#cbd5e1').attr('stroke-width',1.5);
    const label=svg.append('text').attr('x',labelWidth-10).attr('y',y(item.key)+11).attr('text-anchor','end').attr('font-size',9.2).attr('fill','#475569');
    setSvgProjectLabel(label,item.row,{suffix:locationText(item.row)?` | ${locationText(item.row)}`:``,});
    svg.append('text').attr('x',labelWidth-10).attr('y',y(item.key)+23).attr('text-anchor','end').attr('font-size',8.6).attr('fill','#64748b').text(`Seed ${text(item.row['Seed Input'])} | K-mer ${text(item.row['K-mer'])}`);

    markers.forEach(marker=>{
      const value=item.values.get(marker);
      const stats=markerStats.get(marker);
      const minimum=stats.minimum;
      const maximum=stats.maximum;
      const columnX=x(marker);
      const columnWidth=x.bandwidth();
      if(value===undefined||value===null){
        svg.append('rect').attr('x',columnX).attr('y',y(item.key)).attr('width',columnWidth).attr('height',y.bandwidth()).attr('fill','#f1f5f9').attr('stroke','#ffffff').attr('stroke-width',.5);
        return;
      }
      const ratio=minimum===maximum?0.5:(value-minimum)/(maximum-minimum);
      const fill=d3.interpolateCividis(Math.max(0,Math.min(1,ratio)));
      svg.append('rect').attr('x',columnX).attr('y',y(item.key)).attr('width',columnWidth).attr('height',y.bandwidth()).attr('fill',fill).attr('stroke','#ffffff').attr('stroke-width',.5).on('mousemove',event=>hover(event,`<b>${esc(marker)}</b><br>${projectDisplayHtml(item.row)}${locationText(item.row)?`<br>Location: ${esc(locationText(item.row))}`:''}<br>Seed: ${esc(item.row['Seed Input'])}<br>K-mer: ${esc(item.row['K-mer'])}<br>Length: ${d3.format(',d')(Math.round(value))} bp<br>Marker min: ${d3.format(',d')(Math.round(minimum))} bp<br>Marker max: ${d3.format(',d')(Math.round(maximum))} bp`)).on('mouseleave',unhover);
      const rgb=d3.color(fill).rgb();
      const luminance=(0.2126*rgb.r+0.7152*rgb.g+0.0722*rgb.b)/255;
      const numberColor=luminance<0.52?'#ffffff':'#111827';
      const outlineColor=luminance<0.52?'#111827':'#ffffff';
      svg.append('text').attr('x',columnX+columnWidth/2).attr('y',y(item.key)+y.bandwidth()/2+3.5).attr('text-anchor','middle').attr('font-size',8.8).attr('font-weight',800).attr('fill',numberColor).attr('stroke',outlineColor).attr('stroke-width',1.2).attr('paint-order','stroke').attr('pointer-events','none').text(d3.format(',d')(Math.round(value)));
    });
  });

  markers.forEach(marker=>{
    const columnX=x(marker)+x.bandwidth()/2;
    svg.append('text').attr('x',columnX).attr('y',height-26).attr('text-anchor','middle').attr('font-size',9.2).attr('font-weight',700).attr('fill','#0f172a').text(marker);
  });
  svg.append('text').attr('x',(labelWidth+(width-legendWidth-18))/2).attr('y',height-8).attr('text-anchor','middle').attr('font-size',9).attr('fill','#64748b').text('Markers');

  svg.append('text').attr('x',legendX).attr('y',legendY-10).attr('font-size',9.4).attr('font-weight',700).attr('fill','#475569').text('Relative');
  svg.append('rect').attr('x',legendX).attr('y',legendY).attr('width',16).attr('height',legendHeight).attr('rx',3).attr('fill','url(#markerRelativeGradientVertical)');
  svg.append('text').attr('x',legendX+24).attr('y',legendY+8).attr('font-size',8.5).attr('fill','#64748b').text('Max');
  svg.append('text').attr('x',legendX+24).attr('y',legendY+legendHeight).attr('dominant-baseline','ideographic').attr('font-size',8.5).attr('fill','#64748b').text('Min');
}


function renderRepeatTable() {
  const q=document.getElementById('repeatSearch').value.trim().toLowerCase();
  const rows=REPORT.repeats
    .filter(matches)
    .filter(r=>!q||repeatColumns.some(c=>text(r[c]).toLowerCase().includes(q))||projectDisplayText(r).toLowerCase().includes(q))
    .slice()
    .sort((a,b)=>{
      const project=projectDisplayText(a).localeCompare(projectDisplayText(b),undefined,{numeric:true});
      if(project)return project;
      const location=locationText(a).localeCompare(locationText(b),undefined,{numeric:true});
      if(location)return location;
      const seed=text(a['Seed Input']).localeCompare(text(b['Seed Input']),undefined,{numeric:true});
      if(seed)return seed;
      return num(a['K-mer'],0)-num(b['K-mer'],0);
    });
  const maxima=new Map();
  repeatBarColumns.forEach((color,column)=>{ maxima.set(column,d3.max(rows,row=>num(row[column],0))||0); });
  document.getElementById('repeatTableCount').textContent=`${rows.length} repeat${rows.length===1?'':'s'} shown`;
  document.getElementById('repeatTableHead').innerHTML=repeatColumns.map((c,index)=>`<th class="${index<2?'sticky-col':''}">${esc(tableColumnLabel(c))}</th>`).join('');
  let previousProject=null;
  document.getElementById('repeatTableBody').innerHTML=rows.map(r=>{
    const project=text(r['Project name']);
    const projectStart=previousProject!==null&&project!==previousProject;
    previousProject=project;
    const cells=repeatColumns.map(c=>{
      if(c==='Project name')return `<td class="sticky-col">${projectDisplayHtml(r)}</td>`;
      if(c==='Consensus')return `<td><code>${esc(r[c])}</code></td>`;
      if(repeatBarColumns.has(c)){
        const numeric=num(r[c]);
        const maximum=maxima.get(c)||0;
        const percentage=numeric===null||maximum<=0?0:Math.max(0,Math.min(100,100*numeric/maximum));
        return `<td class="data-bar-cell" style="--bar-width:${percentage.toFixed(2)}%;--bar-color:${repeatBarColumns.get(c)}38"><div class="cell-bar"></div><span class="cell-value">${formatNumericMetric(c,numeric)}</span></td>`;
      }
      if(typeof r[c]==='number')return `<td>${formatNumericMetric(c,r[c])}</td>`;
      return `<td class="${c==='Location'?'sticky-col':''}">${esc(r[c])}</td>`;
    }).join('');
    return `<tr class="${projectStart?'project-start':''}">${cells}</tr>`;
  }).join('');
  initResizableTable(document.getElementById('repeatTable'),repeatColumns);
}

function snpRowMatches(row) {
  if (!state.projects.size || !state.projects.has(text(row.project))) return false;
  if (!state.seed.size || !state.seed.has(text(row.seed))) return false;
  if (!state.kmer.size || !state.kmer.has(text(row.kmer))) return false;

  if (!state.status.has('Circularized')) return false;

  const hasRepeat = repeatRunKeys.has(`${text(row.project).trim()}\0${text(row.seed).trim()}\0${normalizedRunValue(row.kmer)}`);
  const repeatStatus = hasRepeat ? 'With repeats' : 'Without repeats';
  if (!state.repeats.size || !state.repeats.has(repeatStatus)) return false;

  return true;
}

function splitSnpPositions(matrix, columnsPerPanel=60) {
  const panels = [];
  for (let start=0; start<matrix.positions.length; start+=columnsPerPanel) {
    panels.push({
      positions: matrix.positions.slice(start,start+columnsPerPanel),
      start,
      end: Math.min(matrix.positions.length,start+columnsPerPanel)
    });
  }
  return panels;
}

function sortSnpRows(rows, referenceId) {
  return rows.slice().sort((a,b)=>{
    if (a.sequence_id === referenceId && b.sequence_id !== referenceId) return -1;
    if (b.sequence_id === referenceId && a.sequence_id !== referenceId) return 1;
    const project = text(a.project).localeCompare(text(b.project), undefined, {numeric:true});
    if (project) return project;
    const kmer = num(a.kmer,0)-num(b.kmer,0);
    if (kmer) return kmer;
    return text(a.sequence_id).localeCompare(text(b.sequence_id), undefined, {numeric:true});
  });
}

function drawSnpLegend(svg, startX, y) {
  const entries = ['A','C','G','T','-','N'];
  const legend = svg.append('g').attr('transform',`translate(${startX},${y})`);
  entries.forEach((base,index)=>{
    const x=index*54;
    legend.append('rect').attr('x',x).attr('y',-10).attr('width',15).attr('height',15).attr('rx',2).attr('fill',snpBaseColors[base]);
    legend.append('text').attr('x',x+21).attr('y',2).attr('font-size',10).attr('fill','#475569').text(base);
  });
}

function selectedSnpReferenceId(matrix) {
  const requested=snpReferenceSelection.get(matrix.marker);
  if(requested&&matrix.rows.some(row=>row.sequence_id===requested))return requested;
  return matrix.reference_sequence_id||matrix.rows[0]?.sequence_id||'';
}

function snpReferenceLabel(row) {
  const main=projectDisplayText({project:row.project,species:row.species});
  const pieces=[main,`Seed ${text(row.seed)}`,`K-mer ${text(row.kmer)}`];
  if(text(row.location))pieces.push(text(row.location));
  return pieces.join(' · ');
}

function referencePositionLabels(matrix,referenceId) {
  const row=matrix.rows.find(item=>item.sequence_id===referenceId);
  if(row&&Array.isArray(row.position_labels)&&row.position_labels.length===matrix.positions.length)return row.position_labels.map(text);
  return matrix.positions.map(text);
}

function parseReferencePosition(value) {
  const source=text(value).trim();
  let match=source.match(/^(\d+)\+(\d+)$/);
  if(match)return {base:Number(match[1]),insertion:Number(match[2]),label:source};
  match=source.match(/^(\d+)$/);
  if(match)return {base:Number(match[1]),insertion:0,label:source};
  return {base:null,insertion:0,label:source};
}

function displayReferencePosition(value) {
  const parsed=parseReferencePosition(value);
  if(parsed.base===0&&parsed.insertion>0)return 'before position 1';
  return parsed.label;
}

function renderSnpPanel(container, matrix, rows, panel, panelIndex, panelCount, referenceId) {
  const labelWidth = 290;
  const cellWidth = 36;
  const rowHeight = 29;
  const projectGap = Math.max(0,num(REPORT_CONFIG.snp_project_gap,12));
  const topSpace = 82;
  const bottomSpace = 132;
  const allReferencePositions=referencePositionLabels(matrix,referenceId);
  const panelPositions=allReferencePositions.slice(panel.start,panel.end);
  const displayedRows = sortSnpRows(rows, referenceId);
  const compactPanel=panelPositions.length<=8;
  const containerWidth=Math.max(360,(container.clientWidth||720)-16);
  const width=compactPanel?containerWidth:Math.max(containerWidth,labelWidth+panelPositions.length*cellWidth+54);

  let yCursor = topSpace;
  let previousProject = null;
  const rowLayout = displayedRows.map((row,index)=>{
    const isReference = row.sequence_id === referenceId;
    if(!isReference && previousProject !== null && text(row.project) !== text(previousProject)) yCursor += projectGap;
    const layout = {row,index,y:yCursor,isReference};
    yCursor += rowHeight;
    if(!isReference) previousProject = row.project;
    return layout;
  });

  const matrixBottom = yCursor;
  const height = matrixBottom + bottomSpace;
  const svg = d3.select(container).append('svg').attr('width',width).attr('height',height).attr('viewBox',`0 0 ${width} ${height}`);
  const matrixX = labelWidth + 16;
  const matrixWidth = panelPositions.length*cellWidth;

  svg.append('text').attr('x',10).attr('y',22).attr('font-size',12).attr('font-weight',700).attr('fill','#0f172a').text(panelCount>1?`Panel ${panelIndex+1}/${panelCount}`:'True SNP positions');
  svg.append('text').attr('x',10).attr('y',39).attr('font-size',10).attr('fill','#64748b').text(`${displayedRows.length} sequences · ${panelPositions.length} SNP columns · coordinates use the selected reference`);
  drawSnpLegend(svg, Math.max(10,width-340), 28);

  rowLayout.forEach(layout=>{
    const background = layout.isReference ? '#dbeafe' : (layout.index%2===0 ? '#eeeeee' : '#ffffff');
    svg.append('rect').attr('x',0).attr('y',layout.y).attr('width',width).attr('height',rowHeight).attr('fill',background);
  });

  const queryLayouts = rowLayout.filter(layout=>!layout.isReference);
  const projectGroups = d3.groups(queryLayouts,layout=>layout.row.project);
  projectGroups.forEach((group,groupIndex)=>{
    if(groupIndex%2!==0)return;
    const first = d3.min(group[1],layout=>layout.y);
    const last = d3.max(group[1],layout=>layout.y);
    svg.append('rect').attr('x',0).attr('y',first).attr('width',width).attr('height',last-first+rowHeight).attr('fill','#bfbfbf').attr('fill-opacity',.20).attr('pointer-events','none');
  });

  rowLayout.forEach(layout=>{
    const row = layout.row;
    const y = layout.y;
    const labelRow={project:row.project,species:row.species};
    const labelMain = projectDisplayText(labelRow);
    const labelSubParts = [`Seed ${text(row.seed)}`, `K-mer ${text(row.kmer)}`];
    if(text(row.location)) labelSubParts.push(text(row.location));
    const labelSelection=svg.append('text').attr('x',10).attr('y',y+12).attr('font-size',10.3).attr('fill','#0f172a');
    setSvgProjectLabel(labelSelection,labelRow,{prefix:layout.isReference?'Reference · ':''});
    svg.append('text').attr('x',10).attr('y',y+24).attr('font-size',9).attr('fill','#64748b').text(labelSubParts.join(' · '));

    panelPositions.forEach((position,j)=>{
      const base = text(row.states[panel.start+j] || 'N').toUpperCase();
      const x = matrixX+j*cellWidth;
      svg.append('rect').attr('x',x).attr('y',y+2).attr('width',cellWidth-2).attr('height',rowHeight-4).attr('rx',3).attr('fill',snpBaseColors[base] || '#cbd5e1').attr('stroke','#ffffff').attr('stroke-width',0.6)
        .on('mousemove',event=>hover(event,`${layout.isReference?'<strong>Reference</strong><br>':''}${projectDisplayHtml(labelRow)}<br>${esc(labelSubParts.join(' · '))}<br>Reference position: ${esc(displayReferencePosition(position))}<br>State: ${esc(base)}`))
        .on('mouseleave',unhover);
      svg.append('text').attr('x',x+(cellWidth-2)/2).attr('y',y+rowHeight/2+4).attr('text-anchor','middle').attr('font-size',10).attr('font-weight',700).attr('fill','#111827').attr('pointer-events','none').text(base);
    });
  });

  panelPositions.forEach((position,j)=>{
    const x = matrixX+j*cellWidth+cellWidth/2;
    svg.append('text').attr('x',x).attr('y',topSpace-12).attr('text-anchor','start').attr('transform',`rotate(-68,${x},${topSpace-12})`).attr('font-size',8.5).attr('fill','#475569').text(displayReferencePosition(position));
  });

  const referenceRow=matrix.rows.find(row=>row.sequence_id===referenceId)||{};
  const markerStart=num(referenceRow.marker_start ?? matrix.marker_start);
  const markerEnd=num(referenceRow.marker_end ?? matrix.marker_end);
  const markerLength=num(referenceRow.marker_length ?? matrix.marker_length_min) || (markerStart!==null&&markerEnd!==null?markerEnd-markerStart+1:null);
  const markerTitle=markerStart!==null&&markerEnd!==null?`Marker ${matrix.marker}: ${d3.format(',d')(Math.round(markerStart))}–${d3.format(',d')(Math.round(markerEnd))} bp · ${d3.format(',d')(Math.round(markerLength))} bp`:`Marker ${matrix.marker} · ${markerLength?d3.format(',d')(Math.round(markerLength))+' bp':'length unavailable'}`;
  const titleWidth=Math.min(300,Math.max(165,markerTitle.length*5.5));
  const barX=titleWidth+22;
  const barWidth=Math.max(220,width-barX-12);
  const barY=matrixBottom+48;

  svg.append('text').attr('x',10).attr('y',barY+11.5).attr('font-size',9.2).attr('font-weight',700).attr('fill','#334155').text(markerTitle);
  svg.append('rect').attr('x',barX).attr('y',barY).attr('width',barWidth).attr('height',16).attr('rx',8).attr('fill','#dbeafe').attr('stroke','#93c5fd');

  const relativeDomainMax=Math.max(1,markerLength||d3.max(panelPositions.map(position=>parseReferencePosition(position).base).filter(value=>value!==null))||1);
  const markerScale=d3.scaleLinear().domain([1,relativeDomainMax]).range([barX,barX+barWidth]);
  panelPositions.forEach((position,j)=>{
    const parsed=parseReferencePosition(position);
    if(parsed.base===null)return;
    const relative=Math.max(1,Math.min(relativeDomainMax,parsed.base+(parsed.insertion?Math.min(.9,parsed.insertion*.05):0)));
    const x=markerScale(relative);
    const sourceX=matrixX+j*cellWidth+(cellWidth-2)/2;
    const genomic=markerStart!==null?markerStart+Math.max(0,parsed.base-1):null;
    const elbowY=barY-18-(j%3)*6;
    svg.append('path').attr('d',`M${sourceX},${matrixBottom+8} V${elbowY} H${x} V${barY}`).attr('fill','none').attr('stroke','#cbd5e1').attr('stroke-width',1);
    svg.append('line').attr('x1',x).attr('x2',x).attr('y1',barY-4).attr('y2',barY+20).attr('stroke','#1d4ed8').attr('stroke-width',1.4)
      .on('mousemove',event=>hover(event,`<b>${esc(matrix.marker)}</b><br>Reference position: ${esc(displayReferencePosition(position))}${genomic!==null?`<br>Approx. genomic coordinate: ${d3.format(',d')(Math.round(genomic))} bp`:''}`)).on('mouseleave',unhover);
  });
  svg.append('text').attr('x',barX).attr('y',barY+34).attr('font-size',8.5).attr('fill','#64748b').text(markerStart!==null?`Start ${d3.format(',d')(Math.round(markerStart))}`:'Relative position 1');
  svg.append('text').attr('x',barX+barWidth).attr('y',barY+34).attr('text-anchor','end').attr('font-size',8.5).attr('fill','#64748b').text(markerEnd!==null?`End ${d3.format(',d')(Math.round(markerEnd))}`:`Position ${d3.format(',d')(Math.round(relativeDomainMax))}`);
}

function renderSnpMatrices() {
  const gallery=document.getElementById('snpGallery');
  gallery.innerHTML='';

  if(!state.status.has('Circularized')){
    document.getElementById('snpSubtitle').textContent='Marker SNP analysis is generated from circularized assemblies; the current status selection excludes circularized runs.';
    gallery.innerHTML='<div class="card empty">No SNP matrix for the current assembly-status selection.</div>';
    return;
  }

  const matrices=REPORT.snp_matrices||[];
  const columnsPerPanel=Math.max(1,num(REPORT_CONFIG.snp_columns_per_panel,60));
  let rendered=0;

  matrices.forEach(matrix=>{
    const referenceId=selectedSnpReferenceId(matrix);
    let rows=matrix.rows.filter(snpRowMatches);
    const reference=matrix.rows.find(row=>row.sequence_id===referenceId);
    if(rows.length&&reference&&!rows.some(row=>row.sequence_id===reference.sequence_id))rows=[reference,...rows];
    if(!rows.length)return;

    const card=document.createElement('div');
    card.className='card snp-card';
    if(matrix.positions.length>Math.max(1,num(REPORT_CONFIG.snp_compact_max_columns,14)))card.classList.add('snp-card-wide');

    const title=document.createElement('div');
    title.className='snp-card-head';
    const options=matrix.rows.map(row=>`<option value="${esc(row.sequence_id)}" ${row.sequence_id===referenceId?'selected':''}>${esc(snpReferenceLabel(row))}</option>`).join('');
    title.innerHTML=`<div><div class="snp-card-title">${esc(matrix.marker)}</div><div class="snp-card-meta">${matrix.snp_count} true SNP${matrix.snp_count===1?'':'s'} · select a reference to recalculate the displayed coordinate labels</div></div><div class="snp-reference-control"><label>Reference</label><select aria-label="Reference for ${esc(matrix.marker)}">${options}</select></div>`;
    const select=title.querySelector('select');
    select.addEventListener('change',()=>{ snpReferenceSelection.set(matrix.marker,select.value); renderSnpMatrices(); renderSamplingMap(); });
    card.appendChild(title);

    const panels=splitSnpPositions(matrix,columnsPerPanel);
    panels.forEach((panel,index)=>{
      const scroll=document.createElement('div'); scroll.className='snp-chart-scroll'; if(panel.positions.length<=8)scroll.classList.add('compact'); card.appendChild(scroll);
      renderSnpPanel(scroll,matrix,rows,panel,index,panels.length,referenceId);
    });
    gallery.appendChild(card); rendered++;
  });

  document.getElementById('snpSubtitle').textContent=rendered
    ? `${rendered} marker SNP matrix${rendered===1?'':' matrices'} rendered as SVG with D3. Each marker has an independent reference selector; metadata species and locations are shown when available.`
    : 'No marker with true SNPs matches the current filters.';
  if(!rendered)gallery.innerHTML='<div class="card empty">No true-SNP matrix matches the current filters.</div>';
}


function selectedMapMarkers() {
  return new Set([...mapSelectedMarkers].filter(marker=>mapAvailableMarkers.includes(marker)));
}

function snpStatsByProject(markerSelection=selectedMapMarkers()) {
  const stats=new Map();
  (REPORT.snp_matrices||[]).forEach(matrix=>{
    if(!markerSelection.size||!markerSelection.has(text(matrix.marker)))return;
    const referenceId=selectedSnpReferenceId(matrix);
    const reference=matrix.rows.find(row=>row.sequence_id===referenceId);
    if(!reference)return;
    matrix.rows.filter(row=>row.sequence_id!==referenceId&&snpRowMatches(row)).forEach(row=>{
      const project=text(row.project).trim();
      if(!stats.has(project))stats.set(project,{differences:0,markers:new Map(),calls:0});
      const item=stats.get(project);
      let markerDifferences=0;
      row.states.forEach((state,index)=>{
        const ref=text(reference.states[index]).toUpperCase();
        const query=text(state).toUpperCase();
        if(query&&ref&&query!==ref){ item.differences+=1; markerDifferences+=1; }
        item.calls+=1;
      });
      if(markerDifferences>0)item.markers.set(text(matrix.marker),(item.markers.get(text(matrix.marker))||0)+markerDifferences);
    });
  });
  return stats;
}

function markerDifferenceSummary(markers) {
  const entries=markers instanceof Map?[...markers.entries()]:[];
  if(!entries.length)return '<span style="color:#94a3b8">No differences in the selected markers</span>';
  return entries.sort((a,b)=>b[1]-a[1]||text(a[0]).localeCompare(text(b[0]),undefined,{numeric:true})).map(([marker,count])=>`<div><strong>${esc(marker)}</strong>: ${count} SNP${count===1?'':'s'}</div>`).join('');
}

function mapRunKey(row) {
  return `${text(row.project).trim()}\0${text(row.seed).trim()}\0${normalizedRunValue(row.kmer)}`;
}

function hammingDistance(a,b) {
  let distance=0,compared=0;
  const markers=new Set([...a.states.keys(),...b.states.keys()]);
  markers.forEach(marker=>{
    const first=a.states.get(marker),second=b.states.get(marker);
    if(!first||!second)return;
    const length=Math.min(first.length,second.length);
    for(let index=0;index<length;index++){
      const x=text(first[index]).toUpperCase(),y=text(second[index]).toUpperCase();
      if(!x||!y||x==='?'||y==='?'||x==='N'||y==='N')continue;
      compared+=1;
      if(x!==y)distance+=1;
    }
  });
  return compared?distance:null;
}

function buildHaplotypeNetworkData(markerSelection=selectedMapMarkers()) {
  if(!markerSelection.size)return {nodes:[],edges:[],sampleToHaplotype:new Map(),excludedSamples:0};
  const samples=new Map();
  (REPORT.snp_matrices||[]).forEach(matrix=>{
    const marker=text(matrix.marker);
    if(!markerSelection.has(marker))return;
    matrix.rows.filter(snpRowMatches).forEach(row=>{
      const key=mapRunKey(row);
      if(!samples.has(key))samples.set(key,{key,project:text(row.project).trim(),seed:text(row.seed),kmer:text(row.kmer),species:text(row.species),location:text(row.location),states:new Map()});
      samples.get(key).states.set(marker,(row.states||[]).map(state=>text(state).toUpperCase()));
    });
  });
  const completeSamples=[...samples.values()].filter(sample=>[...markerSelection].every(marker=>sample.states.has(marker)));
  const excludedSamples=samples.size-completeSamples.length;
  const groups=new Map();
  completeSamples.forEach(sample=>{
    const signature=[...markerSelection].sort((a,b)=>a.localeCompare(b,undefined,{numeric:true})).map(marker=>`${marker}:${sample.states.get(marker).join('')}`).join('|');
    if(!groups.has(signature))groups.set(signature,{signature,samples:[],states:sample.states});
    groups.get(signature).samples.push(sample);
  });
  const nodes=[...groups.values()].sort((a,b)=>b.samples.length-a.samples.length||a.signature.localeCompare(b.signature)).map((group,index)=>({id:`H${index+1}`,signature:group.signature,samples:group.samples,states:group.states,count:group.samples.length,projects:[...new Set(group.samples.map(sample=>sample.project))],locations:[...new Set(group.samples.map(sample=>sample.location).filter(Boolean))]}));
  const sampleToHaplotype=new Map();
  nodes.forEach(node=>node.samples.forEach(sample=>sampleToHaplotype.set(sample.key,node.id)));
  const edges=[];
  if(nodes.length>1){
    const connected=new Set([0]);
    while(connected.size<nodes.length){
      let best=null;
      connected.forEach(i=>{ for(let j=0;j<nodes.length;j++){ if(connected.has(j))continue; const distance=hammingDistance(nodes[i],nodes[j]); if(distance===null)continue; if(!best||distance<best.distance)best={i,j,distance}; } });
      if(!best){ const next=[...Array(nodes.length).keys()].find(index=>!connected.has(index)); if(next===undefined)break; const first=[...connected][0]; edges.push({source:nodes[first].id,target:nodes[next].id,distance:null}); connected.add(next); }
      else { edges.push({source:nodes[best.i].id,target:nodes[best.j].id,distance:best.distance}); connected.add(best.j); }
    }
  }
  return {nodes,edges,sampleToHaplotype,excludedSamples};
}

function renderMapMarkerControls() {
  const container=document.getElementById('mapMarkerControls');
  if(!container)return;
  if(!mapAvailableMarkers.length){ container.innerHTML='<span class="map-analysis-copy">No SNP markers available.</span>'; return; }
  container.innerHTML=mapAvailableMarkers.map(marker=>`<label class="map-marker-option"><input type="checkbox" value="${esc(marker)}" ${mapSelectedMarkers.has(marker)?'checked':''}> ${esc(marker)}</label>`).join('');
  container.querySelectorAll('input[type="checkbox"]').forEach(input=>input.addEventListener('change',()=>{ if(input.checked)mapSelectedMarkers.add(input.value); else mapSelectedMarkers.delete(input.value); renderSamplingMap(); }));
}

function initSamplingMapControls() {
  renderMapMarkerControls();
  const selectAll=document.getElementById('mapSelectAllMarkers'),clear=document.getElementById('mapClearMarkers'),toggle=document.getElementById('mapHaplotypeToggle');
  if(selectAll&&!selectAll.dataset.bound){ selectAll.dataset.bound='1'; selectAll.addEventListener('click',()=>{ mapAvailableMarkers.forEach(marker=>mapSelectedMarkers.add(marker)); renderMapMarkerControls(); renderSamplingMap(); }); }
  if(clear&&!clear.dataset.bound){ clear.dataset.bound='1'; clear.addEventListener('click',()=>{ mapSelectedMarkers.clear(); renderMapMarkerControls(); renderSamplingMap(); }); }
  if(toggle&&!toggle.dataset.bound){ toggle.dataset.bound='1'; toggle.checked=mapShowHaplotypeNetwork; toggle.addEventListener('change',()=>{ mapShowHaplotypeNetwork=toggle.checked; renderSamplingMap(); }); }
}

function renderHaplotypeNetwork(network) {
  const panel=document.getElementById('haplotypeNetworkPanel');
  if(!panel)return;
  panel.classList.toggle('active',mapShowHaplotypeNetwork);
  if(!mapShowHaplotypeNetwork){ panel.innerHTML=''; return; }
  const exclusionNote=network.excludedSamples?` ${network.excludedSamples} sequence${network.excludedSamples===1?' was':'s were'} excluded because not all selected markers were available.`:'';
  panel.innerHTML=`<div class="haplotype-network-head"><div><div class="haplotype-network-title">SNP haplotype network</div><div class="haplotype-network-copy">Node size = sequences. Edge label = SNP distance in the minimum-spanning network.${exclusionNote}</div></div></div><div class="haplotype-network-body"></div>`;
  const body=panel.querySelector('.haplotype-network-body');
  if(!network.nodes.length){ body.innerHTML='<div class="haplotype-network-empty">No haplotypes can be built from the current project, run and marker filters.</div>'; return; }
  const width=370,height=270,cx=width/2,cy=height/2+4;
  const svg=d3.select(body).append('svg').attr('viewBox',`0 0 ${width} ${height}`);
  const nodes=network.nodes.map((node,index)=>{ const angle=(Math.PI*2*index)/Math.max(1,network.nodes.length)-Math.PI/2; const radius=network.nodes.length<=3?72:network.nodes.length<=8?92:108; return {...node,x:network.nodes.length===1?cx:cx+Math.cos(angle)*radius,y:network.nodes.length===1?cy:cy+Math.sin(angle)*radius}; });
  const byId=new Map(nodes.map(node=>[node.id,node]));
  const nodeRadius=d3.scaleSqrt().domain([1,d3.max(nodes,node=>node.count)||1]).range([10,24]);
  const color=d3.scaleOrdinal(nodes.map(node=>node.id),palette);
  network.edges.forEach(edge=>{ const source=byId.get(edge.source),target=byId.get(edge.target); if(!source||!target)return; svg.append('line').attr('x1',source.x).attr('y1',source.y).attr('x2',target.x).attr('y2',target.y).attr('stroke','#94a3b8').attr('stroke-width',1.4); if(edge.distance!==null)svg.append('text').attr('x',(source.x+target.x)/2).attr('y',(source.y+target.y)/2-4).attr('text-anchor','middle').attr('font-size',8.5).attr('font-weight',700).attr('fill','#475569').attr('paint-order','stroke').attr('stroke','#fff').attr('stroke-width',3).text(edge.distance); });
  const nodeGroup=svg.selectAll('g.haplotype-node').data(nodes).join('g').attr('class','haplotype-node').attr('transform',node=>`translate(${node.x},${node.y})`).on('mousemove',(event,node)=>hover(event,`<strong>${esc(node.id)}</strong><br>${node.count} sequence${node.count===1?'':'s'}<br>Projects: ${node.projects.map(project=>projectDisplayHtml(projectRecord(project))).join(', ')}${node.locations.length?`<br>Locations: ${node.locations.map(esc).join(', ')}`:''}`)).on('mouseleave',unhover);
  nodeGroup.append('circle').attr('r',node=>nodeRadius(node.count)).attr('fill',node=>color(node.id)).attr('fill-opacity',.9).attr('stroke','#0f172a').attr('stroke-width',1.2);
  nodeGroup.append('text').attr('text-anchor','middle').attr('dy','0.35em').attr('font-size',9).attr('font-weight',800).attr('fill','#fff').attr('paint-order','stroke').attr('stroke','rgba(15,23,42,.45)').attr('stroke-width',2).text(node=>node.id);
  nodeGroup.append('text').attr('text-anchor','middle').attr('y',node=>nodeRadius(node.count)+12).attr('font-size',8.2).attr('fill','#475569').text(node=>`n=${node.count}`);
}

function parseCoordinateJs(value) {
  const numeric=num(value);
  if(numeric!==null)return numeric;
  const source=text(value).trim().replace(',','.');
  const match=source.match(/(\d+)°\s*(\d+)'\s*([\d.]+)\"?\s*([NSEOWO])/i);
  if(!match)return null;
  let decimal=Number(match[1])+Number(match[2])/60+Number(match[3])/3600;
  if(['S','W','O'].includes(match[4].toUpperCase()))decimal*=-1;
  return decimal;
}

function webMercatorWorld(lon,lat) {
  const clippedLat=Math.max(-85.05112878,Math.min(85.05112878,lat));
  const x=(lon+180)/360;
  const rad=clippedLat*Math.PI/180;
  const y=(1-Math.log(Math.tan(rad)+1/Math.cos(rad))/Math.PI)/2;
  return [x,y];
}

let samplingMapLibreMap = null;
let samplingMapPopup = null;

function mapTilerStyleUrl() {
  const styleBase=text(REPORT_CONFIG.maptiler_style_url || 'https://api.maptiler.com/maps/outdoor-v4/style.json').trim();
  const key=text(REPORT_CONFIG.maptiler_api_key).trim();
  if(!key)return null;
  const separator=styleBase.includes('?')?'&':'?';
  return `${styleBase}${separator}key=${encodeURIComponent(key)}`;
}

function mapLibreRuntimeReady() {
  return Boolean(window.maplibregl && typeof window.maplibregl.Map==='function');
}

function samplingMapRows() {
  const visibleProjects=new Set(REPORT.summary.filter(matches).map(row=>text(row['Project name']).trim()));
  const candidateRows=[];
  (REPORT.metadata_points||[]).forEach(row=>candidateRows.push(row));
  metadataByProject.forEach(row=>candidateRows.push(row));
  const byProject=new Map();
  candidateRows.forEach(row=>{ const project=text(row['Project name']).trim(); if(!project||!visibleProjects.has(project))return; const latitude=parseCoordinateJs(row['Latitude decimal'] ?? row['Latitude']); const longitude=parseCoordinateJs(row['Longitude decimal'] ?? row['Longitude']); if(latitude===null||longitude===null)return; byProject.set(project,{...projectRecord(project),...row,'Latitude decimal':latitude,'Longitude decimal':longitude}); });
  const markerSelection=selectedMapMarkers();
  const snpStats=snpStatsByProject(markerSelection);
  const network=buildHaplotypeNetworkData(markerSelection);
  const haplotypesByProject=new Map();
  network.sampleToHaplotype.forEach((haplotypeId,runKey)=>{
    const project=text(runKey).split('\0')[0];
    if(!haplotypesByProject.has(project))haplotypesByProject.set(project,new Set());
    haplotypesByProject.get(project).add(haplotypeId);
  });
  const grouped=new Map();
  [...byProject.values()].forEach(point=>{
    const lat=num(point['Latitude decimal']),lon=num(point['Longitude decimal']);
    const key=`${locationText(point)||'Unknown'}|${lat.toFixed(6)}|${lon.toFixed(6)}`;
    if(!grouped.has(key))grouped.set(key,{location:locationText(point)||'Unknown',latitude:lat,longitude:lon,projects:[],differences:0,markers:new Map(),haplotypes:new Set()});
    const group=grouped.get(key),project=text(point['Project name']).trim();
    group.projects.push(point);
    const stats=snpStats.get(project)||{differences:0,markers:new Map()};
    group.differences+=stats.differences||0;
    (stats.markers||new Map()).forEach((count,marker)=>group.markers.set(marker,(group.markers.get(marker)||0)+count));
    (haplotypesByProject.get(project)||new Set()).forEach(haplotypeId=>group.haplotypes.add(haplotypeId));
  });
  return {points:[...grouped.values()],projectCount:byProject.size,network};
}

function samplingPointPopupHtml(point) {
  const markerRows=markerDifferenceSummary(point.markers);
  const haplotypes=point.haplotypes&&point.haplotypes.size?`<br><br>Haplotypes: <strong>${[...point.haplotypes].sort().map(esc).join(', ')}</strong>`:'';
  return `<strong>${esc(point.location)}</strong><br>${point.projects.map(project=>projectDisplayHtml(project)).join('<br>')}<br><br>SNP differences: <strong>${point.differences}</strong><br>Markers with differences: <strong>${point.markers.size}</strong><div style="margin-top:5px;padding-top:5px;border-top:1px solid rgba(148,163,184,.35)">${markerRows}</div>${haplotypes}<br><br>${point.latitude.toFixed(6)}, ${point.longitude.toFixed(6)}`;
}

function samplingPointsGeoJson(points) {
  return {type:'FeatureCollection',features:points.map((point,index)=>({type:'Feature',id:index,geometry:{type:'Point',coordinates:[point.longitude,point.latitude]},properties:{pointIndex:index,location:point.location,latitude:point.latitude,longitude:point.longitude,differences:point.differences,markers:point.markers.size,projectHtml:point.projects.map(project=>projectDisplayHtml(project)).join('<br>')}}))};
}

function renderSamplingMapFallback(container,status,points) {
  container.innerHTML='';
  const width=Math.max(620,container.clientWidth||900);
  const height=Math.max(460,container.clientHeight||520);
  const svg=d3.select(container).append('svg').attr('viewBox',`0 0 ${width} ${height}`).attr('width','100%').attr('height','100%');
  svg.append('rect').attr('width',width).attr('height',height).attr('fill','#e8eef2');

  const featurePoints=points.map(point=>({type:'Feature',geometry:{type:'Point',coordinates:[point.longitude,point.latitude]}}));
  const projection=d3.geoMercator().fitExtent([[36,34],[width-36,height-46]],{type:'FeatureCollection',features:featurePoints});
  const path=d3.geoPath(projection);
  if(WORLD_BASEMAP && Array.isArray(WORLD_BASEMAP.features)){
    svg.append('g').selectAll('path').data(WORLD_BASEMAP.features).join('path').attr('d',path).attr('fill','#f8fafc').attr('stroke','#94a3b8').attr('stroke-width',.7);
  }
  const maximumDifferences=d3.max(points,point=>point.differences)||1;
  const radius=d3.scaleSqrt().domain([0,maximumDifferences]).range([7,19]);
  const color=d3.scaleSequential(d3.interpolateYlOrRd).domain([0,maximumDifferences]);
  points.forEach(point=>{
    const xy=projection([point.longitude,point.latitude]);
    if(!xy)return;
    const popup=samplingPointPopupHtml(point);
    svg.append('circle').attr('cx',xy[0]).attr('cy',xy[1]).attr('r',radius(point.differences)).attr('fill',color(point.differences)).attr('fill-opacity',.92).attr('stroke','#ffffff').attr('stroke-width',1.5).on('mousemove',event=>hover(event,popup)).on('mouseleave',unhover);
  });
  status.textContent='MapLibre/MapTiler could not be initialized. A local geographic fallback is shown, but detailed Outdoor v4 basemap data require internet access to api.maptiler.com.';
}

function renderSamplingMap() {
  const container=document.getElementById('samplingMap');
  const status=document.getElementById('mapStatus');
  if(!container||!status)return;

  if(samplingMapPopup){ samplingMapPopup.remove(); samplingMapPopup=null; }
  if(samplingMapLibreMap){ samplingMapLibreMap.remove(); samplingMapLibreMap=null; }
  container.innerHTML='';

  const {points,projectCount,network}=samplingMapRows();
  renderHaplotypeNetwork(network);
  const markerCount=selectedMapMarkers().size;
  document.getElementById('mapSubtitle').textContent=points.length?`${points.length} sampling localit${points.length===1?'y':'ies'} with ${projectCount} project${projectCount===1?'':'s'} using ${markerCount} selected SNP marker${markerCount===1?'':'s'}.`:(REPORT.metadata_available?'Metadata were loaded, but no valid coordinates match the current project filters.':'No metadata were loaded.');
  if(!points.length){ status.textContent='No valid coordinates are available. Expected metadata fields are Project name, Location, Latitude and Longitude.'; return; }

  const styleUrl=mapTilerStyleUrl();
  if(!styleUrl){
    status.textContent='MapTiler API key is not configured. Set html_report.maptiler_api_key in config.yml or MAPTILER_API_KEY when generating the report.';
    renderSamplingMapFallback(container,status,points);
    return;
  }
  if(!mapLibreRuntimeReady()){
    renderSamplingMapFallback(container,status,points);
    return;
  }

  const map=new maplibregl.Map({
    container,
    style:styleUrl,
    center:[points[0].longitude,points[0].latitude],
    zoom:points.length===1?num(REPORT_CONFIG.map_single_point_zoom,16):12,
    maxZoom:num(REPORT_CONFIG.map_max_zoom,20),
    attributionControl:true,
    interactive:true,
    dragRotate:false,
    pitchWithRotate:false,
    antialias:true
  });
  samplingMapLibreMap=map;
  map.addControl(new maplibregl.NavigationControl({showCompass:false,visualizePitch:false}),'top-left');
  map.addControl(new maplibregl.ScaleControl({maxWidth:130,unit:'metric'}),'bottom-left');

  const geojson=samplingPointsGeoJson(points);
  const maximumDifferences=d3.max(points,point=>point.differences)||1;

  map.on('load',()=>{
    map.addSource('sampling-points',{type:'geojson',data:geojson});
    map.addLayer({
      id:'sampling-points-halo',
      type:'circle',
      source:'sampling-points',
      paint:{
        'circle-radius':['interpolate',['linear'],['get','differences'],0,8,maximumDifferences,22],
        'circle-color':'rgba(255,255,255,0.96)',
        'circle-stroke-width':0
      }
    });
    map.addLayer({
      id:'sampling-points',
      type:'circle',
      source:'sampling-points',
      paint:{
        'circle-radius':['interpolate',['linear'],['get','differences'],0,6,maximumDifferences,19],
        'circle-color':['interpolate',['linear'],['get','differences'],0,'#fee8c8',Math.max(1,maximumDifferences*.5),'#fdbb84',maximumDifferences,'#e34a33'],
        'circle-stroke-color':'#0f172a',
        'circle-stroke-width':1.2,
        'circle-opacity':0.92
      }
    });
    map.addLayer({
      id:'sampling-point-labels',
      type:'symbol',
      source:'sampling-points',
      layout:{
        'text-field':['to-string',['get','differences']],
        'text-size':10,
        'text-font':['Noto Sans Bold'],
        'text-allow-overlap':true,
        'text-ignore-placement':true
      },
      paint:{
        'text-color':'#111827',
        'text-halo-color':'rgba(255,255,255,0.85)',
        'text-halo-width':1
      }
    });

    const bounds=new maplibregl.LngLatBounds();
    points.forEach(point=>bounds.extend([point.longitude,point.latitude]));
    if(points.length===1){
      map.jumpTo({center:[points[0].longitude,points[0].latitude],zoom:num(REPORT_CONFIG.map_single_point_zoom,16)});
    }else{
      map.fitBounds(bounds,{padding:55,maxZoom:num(REPORT_CONFIG.map_fit_max_zoom,17),duration:0});
    }
    map.resize();
    status.textContent='MapTiler Outdoor v4 loaded. Point statistics use only the marker chips selected above. Hover or click a point to see which markers carry differences; enable the haplotype network for an additional population-level summary.';
  });

  map.on('mouseenter','sampling-points',()=>{ map.getCanvas().style.cursor='pointer'; });
  map.on('mouseleave','sampling-points',()=>{ map.getCanvas().style.cursor=''; if(samplingMapPopup){samplingMapPopup.remove();samplingMapPopup=null;} });
  map.on('mousemove','sampling-points',event=>{
    const feature=event.features&&event.features[0];
    if(!feature)return;
    const point=points[Number(feature.properties?.pointIndex)];
    if(!point)return;
    const html=samplingPointPopupHtml(point);
    if(samplingMapPopup)samplingMapPopup.remove();
    samplingMapPopup=new maplibregl.Popup({closeButton:false,closeOnClick:false,offset:12,maxWidth:'420px'}).setLngLat(event.lngLat).setHTML(html).addTo(map);
  });
  map.on('click','sampling-points',event=>{
    const feature=event.features&&event.features[0];
    if(!feature)return;
    const point=points[Number(feature.properties?.pointIndex)];
    if(!point)return;
    const html=samplingPointPopupHtml(point);
    new maplibregl.Popup({closeButton:true,closeOnClick:true,offset:12,maxWidth:'420px'}).setLngLat(event.lngLat).setHTML(html).addTo(map);
  });

  map.on('error',event=>{
    const message=event?.error?.message || 'unknown MapTiler/MapLibre error';
    console.warn('MapTiler map error:',message);
    status.textContent=`MapTiler Outdoor v4 reported an error: ${message}. Check internet access and the API key permissions.`;
  });

  setTimeout(()=>{ if(samplingMapLibreMap===map)map.resize(); },120);
}

const tableColumnWidths = new Map();

function initResizableTable(table, columns) {
  if(!table)return;
  const headers=[...table.querySelectorAll('thead th')];
  const defaults={
    'Project name':290,'Location':170,'Seed Input':205,'K-mer':95,'Circularized':120,'Total contigs':115,
    'Smallest contig':155,'Largest contig':155,'Average organelle coverage':205,'Pilon Coverage':145,'Pilon Confirmed %':155,
    'Pilon Corrected snps':165,'Pilon Corrected insertions':190,'Pilon Corrected deletions':185,
    'Repeat length':135,'Period Size':120,'Copy Number':120,'Consensus Size':135,'Percent Matches':145,'Percent Indels':130,
    'Gene context label':230,'Consensus':210
  };
  const tableId=table.id||'table';
  const columnKey=column=>`${tableId}\0${column}`;
  const applyStickyOffsets=()=>{
    let left=0;
    headers.forEach((header,index)=>{
      const sticky=index<2;
      header.classList.toggle('sticky-col',sticky);
      const cells=[...table.querySelectorAll(`tbody tr td:nth-child(${index+1})`)];
      cells.forEach(cell=>cell.classList.toggle('sticky-col',sticky));
      if(sticky){
        header.style.left=`${left}px`;
        cells.forEach(cell=>cell.style.left=`${left}px`);
        left+=(tableColumnWidths.get(columnKey(columns[index]))||parseFloat(header.style.width)||defaults[columns[index]]||140);
      }else{
        header.style.left='';
        cells.forEach(cell=>cell.style.left='');
      }
    });
  };
  const applyTableWidth=()=>{
    const total=headers.reduce((sum,header,index)=>sum+(tableColumnWidths.get(columnKey(columns[index]))||parseFloat(header.style.width)||defaults[columns[index]]||140),0);
    table.style.width=`${Math.max(total,table.parentElement?.clientWidth||0)}px`;
    applyStickyOffsets();
  };
  headers.forEach((header,index)=>{
    const column=columns[index];
    const key=columnKey(column);
    const width=tableColumnWidths.get(key)||defaults[column]||140;
    header.querySelectorAll('.column-resizer').forEach(handle=>handle.remove());
    header.style.width=`${width}px`; header.style.minWidth=`${width}px`; header.style.maxWidth=`${width}px`;
    const handle=document.createElement('span'); handle.className='column-resizer'; handle.setAttribute('aria-hidden','true'); header.appendChild(handle);
    handle.addEventListener('mousedown',event=>{
      if(event.button!==0)return;
      event.preventDefault(); event.stopPropagation(); handle.classList.add('active');
      const startX=event.clientX; const startWidth=header.getBoundingClientRect().width;
      const move=moveEvent=>{ const next=Math.max(72,startWidth+(moveEvent.clientX-startX)); tableColumnWidths.set(key,next); header.style.width=`${next}px`; header.style.minWidth=`${next}px`; header.style.maxWidth=`${next}px`; applyTableWidth(); };
      const up=()=>{ handle.classList.remove('active'); window.removeEventListener('mousemove',move); window.removeEventListener('mouseup',up); };
      window.addEventListener('mousemove',move); window.addEventListener('mouseup',up);
    });
  });
  applyTableWidth();
}

function enableRightButtonDragScroll(container) {
  if(!container || container.dataset.rightDragEnabled==='1')return;
  container.dataset.rightDragEnabled='1';
  let dragging=false,startX=0,startScroll=0;
  container.addEventListener('mousedown',event=>{ if(event.button!==2)return; dragging=true; startX=event.clientX; startScroll=container.scrollLeft; container.classList.add('dragging'); event.preventDefault(); });
  window.addEventListener('mousemove',event=>{ if(!dragging)return; container.scrollLeft=startScroll-(event.clientX-startX); event.preventDefault(); });
  window.addEventListener('mouseup',event=>{ if(!dragging || event.button!==2)return; dragging=false; container.classList.remove('dragging'); });
  container.addEventListener('contextmenu',event=>event.preventDefault());
}

function initStickyFilterLogo() {
  const bar=document.getElementById('filterBar');
  const sentinel=document.getElementById('filterStickySentinel');
  if(!bar || !sentinel || bar.dataset.stickyLogoInitialized==='1')return;
  bar.dataset.stickyLogoInitialized='1';

  const update=()=>{
    const rect=sentinel.getBoundingClientRect();
    bar.classList.toggle('is-stuck',rect.top<0);
  };

  if('IntersectionObserver' in window){
    const observer=new IntersectionObserver(entries=>{
      const entry=entries[0];
      bar.classList.toggle('is-stuck',!entry.isIntersecting && entry.boundingClientRect.top<0);
    },{threshold:[0,1]});
    observer.observe(sentinel);
  }

  window.addEventListener('scroll',update,{passive:true});
  window.addEventListener('resize',update);
  requestAnimationFrame(update);
}

function initStaticTooltips() {
  document.querySelectorAll('[data-tooltip],[data-tooltip-html]').forEach(element=>{
    const content=()=>element.dataset.tooltipHtml || esc(element.dataset.tooltip || '');
    element.addEventListener('mouseenter',event=>hover(event,content()));
    element.addEventListener('mousemove',event=>hover(event,content()));
    element.addEventListener('mouseleave',unhover);
  });
}

function initSectionNavigation() {
  const links=[...document.querySelectorAll('.nav-link')];
  const sections=links.map(link=>document.querySelector(link.getAttribute('href'))).filter(Boolean);

  const observer=new IntersectionObserver(entries=>{
    const visible=entries.filter(entry=>entry.isIntersecting).sort((a,b)=>b.intersectionRatio-a.intersectionRatio)[0];
    if(!visible)return;
    links.forEach(link=>link.classList.toggle('active',link.getAttribute('href')===`#${visible.target.id}`));
  },{rootMargin:'-35% 0px -55% 0px',threshold:[0,.1,.5,1]});

  sections.forEach(section=>observer.observe(section));
}

function renderAll() {
  updateText();
  updateMetrics();
  renderAssemblyOverview();
  updatePilonLayout();
  renderPilonMetrics();
  renderPilonBeforeAfter();
  renderPilonCorrections();
  renderAssemblyTable();
  renderGenomeTimeline();
  renderSamplingMap();
  renderMarkerHeatmap();
  renderRepeatTable();
  renderSnpMatrices();
}

async function start() {
  try {
    await loadD3();
    await loadMapLibre();
    abbreviateSpecies=false;
    document.getElementById('abbreviateSpecies').checked=false;
    renderTabs();
    resetFilterSelections();
    renderAll();
    initStaticTooltips();
    initStickyFilterLogo();
    initMarkerCategoryControls();
    initSamplingMapControls();
    enableRightButtonDragScroll(document.getElementById('assemblyTableScroll'));
    enableRightButtonDragScroll(document.getElementById('repeatTableScroll'));
    initSectionNavigation();

    document.addEventListener('click',closeMultiSelects);
    window.addEventListener('resize',()=>{
      clearTimeout(window.__mocuraResize);
      window.__mocuraResize=setTimeout(renderAll,180);
    });
  } catch (error) {
    showError(`moCURA report could not initialize.\\n${error.message}\\n\\nD3.js could not be initialized. The HTML itself can be opened directly as a local file and does not require a local web server.`);
  }
}

document.getElementById('resetFilters').addEventListener('click',()=>{
  state.assembly=null;
  document.getElementById('assemblySearch').value='';
  document.getElementById('repeatSearch').value='';
  resetFilterSelections();
  renderAll();
});

document.getElementById('abbreviateSpecies').addEventListener('change',event=>{
  abbreviateSpecies=event.target.checked;
  renderTabs();
  renderAll();
});

document.getElementById('assemblySearch').addEventListener('input',renderAssemblyTable);
document.getElementById('repeatSearch').addEventListener('input',renderRepeatTable);

start();
</script>
</body>
</html>"""


def json_for_html(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")


def generate_html_report(**kwargs):
    output_file = kwargs.get("output_file", "moCURA_report.html")
    output_dir = kwargs.get("output_dir") or os.path.dirname(output_file) or "."
    config = kwargs.get("config", {}) or {}
    title = str(config.get("title", "moCURA interactive report"))

    report_data = prepare_html_report_data(
        summary_dataframe=kwargs.get("summary_dataframe"),
        plot_dataframe=kwargs.get("plot_dataframe"),
        genbank_files_dataframe=kwargs.get("genbank_files_dataframe"),
        marker_dataframe=kwargs.get("marker_dataframe"),
        trf_summary_dataframe=kwargs.get("trf_summary_dataframe"),
        trf_repeats_dataframe=kwargs.get("trf_repeats_dataframe"),
        marker_snp_results=kwargs.get("marker_snp_results", {}),
        static_plot_paths=kwargs.get("static_plot_paths", []),
        metadata_dataframe=kwargs.get("metadata_dataframe"),
        metadata_path=kwargs.get("metadata_path") or config.get("metadata_path"),
        output_dir=output_dir
    )

    report_config = {
        "max_repeat_families": int(config.get("max_repeat_families", 18)),
        "snp_columns_per_panel": int(config.get("snp_columns_per_panel", 60)),
        "snp_project_gap": int(config.get("snp_project_gap", 12)),
        "snp_compact_max_columns": int(config.get("snp_compact_max_columns", 14)),
        "pilon_stack_threshold": int(config.get("pilon_stack_threshold", 10)),
        "pilon_height_per_group": int(config.get("pilon_height_per_group", 22)),
        "pilon_max_height": int(config.get("pilon_max_height", 900)),
        "maptiler_api_key": str(os.environ.get("MAPTILER_API_KEY") or config.get("maptiler_api_key", "")),
        "maptiler_style_url": str(config.get("maptiler_style_url", "https://api.maptiler.com/maps/outdoor-v4/style.json")),
        "map_single_point_zoom": int(config.get("map_single_point_zoom", 16)),
        "map_fit_max_zoom": int(config.get("map_fit_max_zoom", 17)),
        "map_max_zoom": int(config.get("map_max_zoom", 20)),
    }
    document = HTML_TEMPLATE.replace("__REPORT_TITLE__", html.escape(title))
    document = document.replace("__LOGO_HTML__", build_logo_html(config))
    document = document.replace("__DATA_JSON__", json_for_html(report_data))
    document = document.replace("__CONFIG_JSON__", json_for_html(report_config))
    document = document.replace("__BASEMAP_JSON__", json_for_html(load_embedded_basemap()))

    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True, mode=0o755)

    with open(output_file, "w", encoding="utf-8") as handle:
        handle.write(document)

    logging.info("HTML report generated with MapTiler Outdoor v4 / MapLibre sampling map support: %s", output_file)
    return output_file
