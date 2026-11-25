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
.shell { min-width: 0; padding: 22px 28px 0; }
.header-wrap { display: flex; gap: 18px; align-items: center; }
.header-brand { flex: 0 0 auto; display: flex; align-items: center; justify-content: center; }
.header-logo { display: block; width: 180px; max-width: 26vw; height: auto; object-fit: contain; }
.header-logo-svg { width: 180px; max-width: 26vw; line-height: 0; }
.header-logo-svg svg { display: block; width: 100%; height: auto; }
.header-text { min-width: 0; }
.eyebrow { color: var(--brand); text-transform: uppercase; letter-spacing: .2em; font-size: 12px; font-weight: 700; }
h1 { margin: 4px 0 0; font-size: 30px; color: #020617; }
.subtitle { margin-top: 8px; color: var(--muted); font-size: 14px; }
.tabs { display: flex; flex-wrap: wrap; gap: 8px; max-height: 104px; overflow-y: auto; padding: 10px 0 12px; border-bottom: 1px solid var(--border); align-items: center; }
.project-tab { white-space: nowrap; border: 1px solid var(--border); background: white; border-radius: 10px; padding: 6px 11px; color: #475569; font-size: 13px; font-weight: 600; flex: 0 0 auto; }
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
.section { margin-top: 30px; scroll-margin-top: 66px; }
.section h2 { margin: 0; color: #020617; font-size: 20px; }
.section-note { margin-top: 4px; color: var(--muted); font-size: 13px; }
.metrics { display: grid; grid-template-columns: repeat(6, minmax(0,1fr)); gap: 12px; }
.card { border: 1px solid var(--border); background: var(--panel); border-radius: 16px; box-shadow: 0 1px 2px rgba(15,23,42,.05); }
.metric { padding: 16px; }
.metric-label { display: flex; gap: 6px; align-items: center; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; font-size: 11px; }
.metric-value { margin-top: 5px; color: #020617; font-size: 24px; font-weight: 700; }
/* Info icon: Font Awesome Free v7.3.1 "circle-info" by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc. */
.info-dot { display: inline-block; flex: 0 0 auto; width: 16px; height: 16px; vertical-align: -3px; font-size: 0; line-height: 0; color: transparent; overflow: hidden; cursor: help; text-transform: none; letter-spacing: 0; background-color: #64748b;
  -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 640 640'%3E%3Cpath d='M320 576C461.4 576 576 461.4 576 320C576 178.6 461.4 64 320 64C178.6 64 64 178.6 64 320C64 461.4 178.6 576 320 576zM288 224C288 206.3 302.3 192 320 192C337.7 192 352 206.3 352 224C352 241.7 337.7 256 320 256C302.3 256 288 241.7 288 224zM280 288L328 288C341.3 288 352 298.7 352 312L352 400L360 400C373.3 400 384 410.7 384 424C384 437.3 373.3 448 360 448L280 448C266.7 448 256 437.3 256 424C256 410.7 266.7 400 280 400L304 400L304 336L280 336C266.7 336 256 325.3 256 312C256 298.7 266.7 288 280 288z'/%3E%3C/svg%3E") center / contain no-repeat;
  mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 640 640'%3E%3Cpath d='M320 576C461.4 576 576 461.4 576 320C576 178.6 461.4 64 320 64C178.6 64 64 178.6 64 320C64 461.4 178.6 576 320 576zM288 224C288 206.3 302.3 192 320 192C337.7 192 352 206.3 352 224C352 241.7 337.7 256 320 256C302.3 256 288 241.7 288 224zM280 288L328 288C341.3 288 352 298.7 352 312L352 400L360 400C373.3 400 384 410.7 384 424C384 437.3 373.3 448 360 448L280 448C266.7 448 256 437.3 256 424C256 410.7 266.7 400 280 400L304 400L304 336L280 336C266.7 336 256 325.3 256 312C256 298.7 266.7 288 280 288z'/%3E%3C/svg%3E") center / contain no-repeat; }
.info-dot:hover { background-color: var(--brand); }
.info-grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 12px; margin-top: 12px; }
.info-card { padding: 14px 15px; border-left: 4px solid var(--brand); }
.info-card:nth-child(2) { border-left-color: var(--secondary); }
.info-card:nth-child(3) { border-left-color: var(--accent); }
.info-title { font-size: 13px; font-weight: 700; color: #0f172a; }
.info-copy { margin-top: 4px; color: var(--muted); font-size: 12px; line-height: 1.45; }
.chart-grid { display: grid; grid-template-columns: minmax(0,1fr); gap: 16px; margin-top: 16px; }
.pilon-grid.stacked { grid-template-columns: 1fr; }
.pilon-grid.stacked .chart { min-height: 520px; }
.assembly-metric-grid { display: grid; grid-template-columns: minmax(0,1.6fr) repeat(3,minmax(0,1fr)); gap: 12px; margin-top: 14px; align-items: stretch; }
.assembly-metric-card .chart-title { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.assembly-metric-card .chart-subtitle { height: 32px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.assembly-species-card, .assembly-metric-card { padding: 10px; min-width: 0; overflow: hidden; display: flex; flex-direction: column; height: 100%; }

.assembly-species-chart, .assembly-metric-chart { width: 100%; overflow: hidden; flex: 1 1 auto; }
.assembly-metric-chart svg { display: block; width: 100%; height: auto; }
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
.tooltip { position: fixed; z-index: 10000; pointer-events: none; opacity: 0; background: #000; color: #fff; padding: 8px 11px; border-radius: 8px; font-size: 12px; line-height: 1.5; max-width: 340px; text-align: justify; hyphens: auto; }
/* Tooltips (Tippy.js): black, justified text. */
.tippy-box[data-theme~='mocura'] { background-color: #000; color: #fff; font-size: 12px; line-height: 1.5; border-radius: 8px; box-shadow: 0 10px 28px rgba(0,0,0,.28); }
.tippy-box[data-theme~='mocura'] > .tippy-content { padding: 8px 11px; text-align: justify; hyphens: auto; }
.tippy-box[data-theme~='mocura'] > .tippy-arrow { color: #000; }
.tippy-box[data-theme~='mocura'] b, .tippy-box[data-theme~='mocura'] strong { color: #fff; }
.table-card { margin-top: 16px; overflow: hidden; }
.table-toolbar { display: flex; flex-direction: column; align-items: stretch; gap: 10px; padding: 14px; border-bottom: 1px solid var(--border); }
.table-title { white-space: nowrap; }
.table-tools { display: flex; gap: 12px; align-items: center; width: 100%; }
.table-search-control { min-width: 0; flex: 1 1 auto; }
.table-search-control .filter-label { justify-content: flex-start; }
.table-search-wrap { position: relative; width: 100%; }
.table-search-wrap svg { position: absolute; left: 11px; top: 50%; transform: translateY(-50%); width: 16px; height: 16px; stroke: #64748b; pointer-events: none; }
.table-search-wrap input[type="search"] { min-width: 0; width: 100%; padding-left: 36px; }
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
table .pinned { position: sticky; z-index: 3; background-color: inherit; }
thead th.pinned { z-index: 7; background: #e2e8f0; }
table .pinned-last { box-shadow: 1px 0 0 #cbd5e1; }
.table-scroll tbody tr:nth-child(odd) td.pinned { background-color: #fff; }
.table-scroll tbody tr:nth-child(even) td.pinned { background-color: var(--stripe); }
.table-scroll tbody tr:hover td.pinned { background-color: var(--brand-soft); }
.ranking-table tr.recommended td.pinned { background-color: #e7f6ef !important; }
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
.snp-grid { display: grid; grid-template-columns: minmax(0,1fr); gap: 18px; margin-top: 14px; }
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
.read-qc-panel { margin-top: 12px; }
.read-qc-panel:empty { display: none; }
.read-qc-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 12px; }
.read-qc-card { padding: 14px 16px; }
.read-qc-card dl { display: grid; grid-template-columns: auto auto; gap: 3px 12px; margin: 8px 0 0; font-size: 12px; }
.read-qc-card dt { color: #64748b; }
.read-qc-card dd { margin: 0; text-align: right; font-weight: 650; font-variant-numeric: tabular-nums; }
.completeness-scroll { overflow-y: auto; overflow-x: hidden; max-height: 760px; }
.completeness-scroll svg { display: block; }
.quality-note { border-left: 3px solid var(--accent); padding: 8px 12px; background: #fff7ed; border-radius: 0 10px 10px 0; font-size: 12.5px; color: #7c2d12; margin: 10px 0 14px; }
.alert-chip { display: inline-block; font-size: 11px; line-height: 1.45; padding: 1px 7px; margin: 1px 3px 1px 0; border-radius: 6px; border: 1px solid #cbd5e1; color: #334155; white-space: nowrap; }
.alert-chip.warning { border-color: #f59e0b; color: #92400e; background: #fffbeb; }
.alert-chip.info { border-color: #93c5fd; color: #1e3a8a; background: #eff6ff; }
.provenance-section { margin-top: 30px; }
.provenance-section > summary { cursor: pointer; font-size: 20px; font-weight: 750; padding: 6px 0; }
.provenance-section table { font-size: 12px; }
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
  .info-grid { grid-template-columns: 1fr; }
  .file-grid { grid-template-columns: repeat(2,minmax(0,1fr)); }
}
@media (max-width: 780px) {
  .shell { padding: 14px; }
  .filters { margin: 0 -14px; padding: 10px 14px; }
  .sticky-filter-row { grid-template-columns: 1fr; }
  .sticky-logo { display: none; }
  .metrics, .chart-grid, .image-grid, .snp-grid, .file-grid, .filter-grid { grid-template-columns: 1fr; }
  .table-toolbar { flex-direction: column; align-items: stretch; }
}

.layout { display: grid; grid-template-columns: 264px minmax(0,1fr); min-height: 100vh; }
.sidebar { position: sticky; top: 0; height: 100vh; overflow-y: auto; display: flex; flex-direction: column; gap: 18px; padding: 18px 16px 22px; background: #ffffff; border-right: 1px solid var(--border); z-index: 50; }
.sidebar-logo { display: flex; justify-content: center; }
.sidebar-logo .header-logo, .sidebar-logo .header-logo-svg { width: 176px; max-width: 100%; }
.sidebar-heading { margin-bottom: 8px; color: #0f172a; font-size: 13px; font-weight: 750; }
.side-filters { display: grid; gap: 10px; }
.side-filters .multi-trigger { min-height: 36px; padding: 6px 9px; font-size: 13px; }
.sidebar .multi-menu { min-width: 0; }
.sidebar .reset { width: 100%; padding: 8px 12px; }
.sidebar .filter-summary { line-height: 1.5; }
.side-nav { display: flex; flex-direction: column; gap: 2px; }
.side-nav a { padding: 7px 10px; border-radius: 8px; color: #475569; font-size: 13px; font-weight: 650; border-left: 3px solid transparent; }
.side-nav a:hover { background: var(--brand-soft); color: var(--brand); }
.side-nav a.active { background: var(--brand-soft); color: #075985; border-left-color: var(--brand); }
.section-bar { position: sticky; top: 0; z-index: 40; display: flex; align-items: center; gap: 10px; margin: 12px -28px 0; padding: 8px 28px; background: rgba(248,250,252,.96); backdrop-filter: blur(8px); border-bottom: 1px solid var(--border); }
.section-bar .nav { margin-top: 0; flex: 1 1 auto; flex-wrap: wrap; overflow: visible; row-gap: 5px; }
.section-bar .nav { gap: 5px; }
.section-bar .nav a { padding: 6px 10px; font-size: 12px; }
.section-bar .species-toggle { padding: 6px 10px; }
.section-bar .species-toggle { margin-left: 0; flex: 0 0 auto; }
.recommendation-grid { display: grid; grid-template-columns: minmax(0,1fr); gap: 10px; padding: 0 14px 14px; }
.reco-card { padding: 14px 16px; border-left: 5px solid #029E73; display: grid; grid-template-columns: minmax(240px,1fr) 128px minmax(460px,2.3fr); gap: 8px 22px; align-items: center; }
.reco-card.hidden-pick { border-left-color: #DE8F05; }
.reco-card.no-pick { border-left-color: #94a3b8; display: block; }
.reco-info { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.reco-card .reco-components { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 10px 22px; align-items: start; }
.reco-metric { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.reco-metric-head { display: flex; align-items: baseline; gap: 8px; font-size: 12px; }
.reco-metric-name { font-weight: 700; color: #0f172a; }
.reco-metric-weight { color: #94a3b8; font-size: 10.5px; }
.reco-metric-value { margin-left: auto; font-weight: 700; color: #0f172a; font-variant-numeric: tabular-nums; }
.reco-metric-help { font-size: 11px; line-height: 1.35; color: #64748b; }
.reco-score-note { font-size: 10.5px; font-weight: 500; color: var(--muted); line-height: 1.3; margin-top: 2px; }
.reco-score-note .info-dot { vertical-align: -1px; }
.ranking-table th.help-head { cursor: help; }
.verdict-chip { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 11.5px; font-weight: 700; white-space: nowrap; background: #e2e8f0; color: #334155; }
.verdict-chip.Confirmed { background: #e7f6ef; color: #05624b; }
.verdict-chip.Ambiguous { background: #fff4e0; color: #92400e; }
.verdict-chip.Not-confirmed { background: #fde8e4; color: #9a3412; }
.verdict-chip.No-reference { background: #f1f5f9; color: #475569; }
.species-table td { vertical-align: top; }
.sp-list { display: grid; gap: 3px; min-width: 390px; }
.sp-hit { display: grid; grid-template-columns: 14px minmax(210px,1fr) 64px 52px; gap: 6px; align-items: center; font-size: 12px; text-align: left; }
.sp-hit .sp-rank { color: #94a3b8; font-size: 10.5px; text-align: right; }
.sp-hit a { color: #0f172a; text-decoration: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sp-hit a:hover { text-decoration: underline; }
.sp-hit.declared a { color: #05624b; font-weight: 750; }
.sp-hit .reco-bar { height: 6px; }
.sp-hit .sp-id { font-variant-numeric: tabular-nums; text-align: right; color: #334155; }
.sp-empty { color: var(--muted); font-size: 12px; }
.reco-species { margin-top: 2px; }
.reco-details { margin-top: 14px; }
.reco-details > summary, .ranking-details > summary { list-style: none; display: flex; align-items: center; gap: 10px; }
.reco-details > summary::-webkit-details-marker, .ranking-details > summary::-webkit-details-marker { display: none; }
.reco-details > summary::before, .ranking-details > summary::before { content: ""; width: 8px; height: 8px; border-right: 2px solid #475569; border-bottom: 2px solid #475569; transform: rotate(-45deg); transition: transform .15s ease; flex: 0 0 auto; }
.reco-details[open] > summary::before, .ranking-details[open] > summary::before { transform: rotate(45deg); }
.reco-details > summary { cursor: pointer; padding: 12px 14px; font-weight: 700; color: #0f172a; }
.summary-count { color: var(--muted); font-weight: 500; font-size: 12px; }
.paths-card { margin-top: 14px; padding: 12px 14px; }
.paths-head { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 14px; margin-bottom: 8px; }
.paths-head .chart-title { margin: 0; }
.paths-options { display: inline-flex; flex-wrap: wrap; gap: 6px; }
.paths-options label { display: inline-flex; align-items: center; gap: 6px; padding: 5px 10px; border: 1px solid #cbd5e1; border-radius: 999px; font-size: 12px; font-weight: 650; color: #475569; cursor: pointer; }
.paths-options label:has(input:checked) { border-color: var(--brand); background: var(--brand-soft); color: #075985; }
.paths-options input { accent-color: var(--brand); margin: 0; }
.copy-button { margin-left: auto; display: inline-flex; align-items: center; gap: 7px; border: 1px solid var(--brand); border-radius: 8px; background: var(--brand); color: #fff; padding: 7px 13px; font-size: 12px; font-weight: 750; }
.copy-button.copied { background: #029E73; border-color: #029E73; }
.copy-button svg { width: 14px; height: 14px; }
#recommendedPaths { width: 100%; resize: vertical; min-height: 70px; border: 1px solid #cbd5e1; border-radius: 10px; padding: 9px 11px; font: 12px/1.55 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; color: #0f172a; background: #f8fafc; white-space: pre; overflow: auto; }
.paths-note { margin-top: 6px; color: var(--muted); font-size: 11.5px; }
.reco-head { display: flex; justify-content: space-between; gap: 10px; align-items: baseline; }
.reco-project { font-size: 13.5px; }
.reco-score { font-size: 26px; font-weight: 800; color: #05624b; font-variant-numeric: tabular-nums; }
.reco-score small { font-size: 12px; color: var(--muted); font-weight: 600; }
.reco-assembly { font-size: 14px; font-weight: 750; color: #0f172a; }
.reco-meta { color: var(--muted); font-size: 12px; line-height: 1.5; }
.reco-components { display: grid; grid-template-columns: auto 1fr auto; gap: 3px 8px; align-items: center; font-size: 11.5px; color: #475569; }
.reco-bar { height: 7px; border-radius: 4px; background: #e2e8f0; overflow: hidden; }
.reco-bar span { display: block; height: 100%; background: #029E73; }
.reco-bar.na span { background: transparent; }
.ranking-details { margin-top: 14px; }
.ranking-details > summary { cursor: pointer; padding: 12px 14px; font-weight: 700; color: #0f172a; }
.ranking-weights { padding: 0 14px 10px; color: var(--muted); font-size: 12px; }
.ranking-table { min-width: 1200px; }
.ranking-table tr.recommended td { background: #e7f6ef !important; font-weight: 650; }
.component-cell { min-width: 92px; }
.component-cell .reco-bar { margin-top: 3px; }
.heatmap-toggle { display: inline-flex; align-items: center; gap: 8px; margin: 2px 0 8px; font-size: 12px; font-weight: 700; color: #475569; cursor: pointer; }
.heatmap-toggle input { accent-color: var(--brand); width: 16px; height: 16px; }
.concordance-grid { display: grid; grid-template-columns: minmax(0,1fr); gap: 14px; margin-top: 14px; }
.concordance-card { padding: 14px; }
.concordance-card svg { display: block; width: 100%; height: auto; }
.rscu-legend { display: flex; flex-wrap: wrap; gap: 6px 14px; margin: 2px 0 8px; font-size: 11.5px; color: #475569; }
.rscu-legend span { display: inline-flex; align-items: center; gap: 6px; }
.rscu-legend i { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
.rscu-scroll { overflow-x: auto; }
.rscu-scroll svg { display: block; }
.composition-controls { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin: 4px 0 10px; font-size: 12px; color: #475569; font-weight: 700; }
.composition-controls select { max-width: 640px; border: 1px solid #cbd5e1; border-radius: 8px; padding: 6px 8px; font-size: 12px; background: #fff; }
.project-picker { margin-top: 16px; position: relative; }
.project-notice { width: 100%; display: flex; align-items: center; gap: 10px; padding: 11px 14px; border: 1px solid #93c5fd; border-radius: 12px; background: #eff6ff; color: #1e3a8a; font-size: 13.5px; text-align: left; }
.project-notice:hover, .project-notice[aria-expanded="true"] { border-color: var(--brand); box-shadow: 0 0 0 3px rgba(1,115,178,.10); }
.project-notice svg { width: 18px; height: 18px; stroke: var(--brand); flex: 0 0 auto; }
.project-notice-action { margin-left: auto; padding: 5px 11px; border-radius: 8px; background: var(--brand); color: #fff; font-size: 12px; font-weight: 750; white-space: nowrap; }
.project-picker-panel { margin-top: 8px; border: 1px solid #cbd5e1; border-radius: 12px; background: #fff; box-shadow: 0 18px 45px rgba(15,23,42,.12); }
.project-picker-panel[hidden] { display: none; }
.project-picker-tools { display: flex; gap: 8px; align-items: center; padding: 12px; border-bottom: 1px solid var(--border); flex-wrap: wrap; }
.project-picker-tools .table-search-wrap { flex: 1 1 280px; }
.project-picker-tools input[type="search"] { padding-left: 36px; }
.picker-action { border: 1px solid #cbd5e1; border-radius: 8px; background: #f8fafc; color: #475569; padding: 8px 11px; font-size: 12px; font-weight: 700; }
.picker-action:hover { border-color: #93c5fd; background: #eff6ff; }
.picker-apply { border: 1px solid var(--brand); border-radius: 8px; background: var(--brand); color: #fff; padding: 8px 14px; font-size: 12px; font-weight: 750; }
.project-picker-list { max-height: 340px; overflow-y: auto; padding: 8px 12px; display: grid; grid-template-columns: repeat(auto-fill,minmax(300px,1fr)); gap: 2px 14px; }
.project-picker-list .multi-option { font-size: 12.5px; }
.project-picker-list .option-meta { margin-left: auto; color: var(--muted); font-size: 11px; white-space: nowrap; }
.project-picker-foot { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 10px 12px; border-top: 1px solid var(--border); }
.project-picker-buttons { display: flex; gap: 8px; }
.genome-legend { display: flex; flex-wrap: wrap; gap: 6px 16px; margin-top: 10px; color: #475569; font-size: 12px; }
.genome-legend span { display: inline-flex; align-items: center; gap: 6px; }
.genome-legend i { display: inline-block; width: 14px; height: 10px; border-radius: 2px; }
.quality-guide { margin-top: 12px; padding: 0; overflow: hidden; }
.quality-guide > summary { cursor: pointer; padding: 12px 14px; font-weight: 700; color: #0f172a; font-size: 13.5px; }
.quality-guide-grid { display: grid; grid-template-columns: repeat(auto-fit,minmax(260px,1fr)); gap: 0; border-top: 1px solid var(--border); }
.quality-guide-group { padding: 12px 14px; border-right: 1px solid var(--border); border-bottom: 1px solid var(--border); }
.quality-guide-group h4 { margin: 0 0 6px; font-size: 12.5px; color: #0f172a; }
.quality-guide-group dl { margin: 0; display: grid; gap: 5px; font-size: 12px; line-height: 1.45; }
.quality-guide-group dt { font-weight: 700; color: #334155; }
.quality-guide-group dd { margin: 0 0 4px; color: var(--muted); text-align: justify; }
.quality-legend { display: flex; flex-wrap: wrap; gap: 6px 16px; padding: 10px 14px; font-size: 12px; color: #475569; }
.quality-legend span { display: inline-flex; align-items: center; gap: 6px; }
.quality-legend i { width: 14px; height: 14px; border-radius: 4px; display: inline-block; }
#qualityTable { min-width: 100%; width: max-content; font-size: 12.5px; }
#qualityTable thead tr.column-head th { min-width: 84px; }
#qualityTable thead tr.column-head th.q-sticky { min-width: 170px; }
#qualityTable thead tr.column-head th { cursor: help; }
#qualityTable td.q-num { text-align: right; font-variant-numeric: tabular-nums; }
#qualityTable td.pinned:not(.q-ok):not(.q-warn):not(.q-bad) { background: #fff; }
#qualityTable td.q-project-cell { text-align: left; white-space: nowrap; }
#qualityTable th, #qualityTable td { padding: 6px 8px; }
#qualityTable thead tr.group-head th { top: 0; background: #cbd5e1; color: #1e293b; text-align: center; border-left: 2px solid #f8fafc; }
#qualityTable thead tr.column-head th { top: 31px; text-transform: none; letter-spacing: 0; font-size: 11.5px; white-space: normal; line-height: 1.25; vertical-align: bottom; border-left: 1px solid #f1f5f9; }
#qualityTable tbody td { vertical-align: middle; }
#qualityTable td.q-run { text-align: left; white-space: nowrap; }
#qualityTable td.q-alerts { text-align: left; white-space: normal; min-width: 280px; max-width: 420px; }
#qualityTable td.q-alerts .alert-chip { white-space: normal; max-width: 100%; font-size: 10.5px; }
#qualityTable .data-bar-cell { min-width: 0; }
#qualityTable tr.q-project td { background: #e8f3f9 !important; text-align: left; font-size: 13px; border-top: 14px solid var(--bg); }
tr.q-project td > .row-head { position: sticky; left: 10px; display: inline-block; }
#qualityTable td.q-ok { background: #e7f6ef !important; color: #05624b; }
#qualityTable td.q-warn { background: #fff4e0 !important; color: #92400e; font-weight: 650; }
#qualityTable td.q-bad { background: #fde8e4 !important; color: #9a3412; font-weight: 700; }
.q-sub { display: block; color: var(--muted); font-size: 11px; font-weight: 400; }
.quality-only-alerts { display: inline-flex; align-items: center; gap: 8px; font-size: 12px; color: #475569; font-weight: 650; }
.snp-toolbar { display: flex; flex-wrap: wrap; gap: 10px 18px; align-items: center; margin-top: 12px; padding: 10px 14px; border: 1px solid var(--border); border-radius: 12px; background: #fff; font-size: 12px; color: #475569; }
.snp-toolbar label { display: inline-flex; align-items: center; gap: 8px; font-weight: 700; cursor: pointer; }
.snp-toolbar input { accent-color: var(--brand); width: 16px; height: 16px; }
.snp-hidden-note { margin: 10px 14px 4px; padding: 0; border-left: 3px solid #DE8F05; background: #fffbeb; border-radius: 0 8px 8px 0; color: #92400e; font-size: 12px; line-height: 1.5; }
.snp-hidden-note > summary { cursor: pointer; padding: 8px 12px; }
.snp-hidden-note ul { margin: 0; padding: 0 14px 10px 32px; max-height: 220px; overflow: auto; }
.snp-hidden-note li { margin: 2px 0; }
.snp-reference-control { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #475569; font-weight: 700; }
.snp-reference-control select { max-width: 520px; border: 1px solid #cbd5e1; border-radius: 8px; padding: 6px 8px; background: #fff; font-size: 12px; }
@media (max-width: 1000px) {
  .layout { grid-template-columns: 1fr; }
  .sidebar { position: static; height: auto; border-right: 0; border-bottom: 1px solid var(--border); }
  .side-nav { flex-direction: row; flex-wrap: wrap; }
  .shell { padding: 16px; }
}
/* How-to-read cards: one per chart or table, opened with an animated panel. */
.guide-slot { margin-top: 12px; }
.guide-card { margin: 8px 0 10px; border: 1px solid #cfe3f1; border-radius: 12px; background: linear-gradient(180deg,#f7fbfe 0%,#ffffff 100%); overflow: hidden; transition: border-color .2s ease, box-shadow .2s ease; }
.guide-card:hover { border-color: #93c5fd; }
.guide-card.open { border-color: var(--brand); box-shadow: 0 6px 22px rgba(1,115,178,.10); }
.table-toolbar .guide-card { margin: 2px 0 0; }
.guide-toggle { width: 100%; display: flex; align-items: center; gap: 10px; padding: 9px 12px; border: 0; background: transparent; color: #0f172a; text-align: left; font-size: 12.5px; }
.guide-toggle:focus-visible { outline: 2px solid var(--brand); outline-offset: -2px; border-radius: 12px; }
.guide-icon { flex: 0 0 auto; width: 28px; height: 28px; display: grid; place-items: center; border-radius: 8px; background: var(--brand-soft); color: var(--brand); transition: background .2s ease, color .2s ease, transform .3s ease; }
.guide-icon svg { width: 16px; height: 16px; }
.guide-card.open .guide-icon { background: var(--brand); color: #fff; transform: rotate(-8deg) scale(1.05); }
.guide-label { flex: 0 0 auto; font-weight: 750; color: #075985; }
.guide-summary { min-width: 0; color: #475569; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.guide-chevron { margin-left: auto; flex: 0 0 auto; width: 8px; height: 8px; border-right: 2px solid #475569; border-bottom: 2px solid #475569; transform: rotate(45deg); transition: transform .3s ease; }
.guide-card.open .guide-chevron { transform: rotate(-135deg); }
.guide-panel { display: grid; grid-template-rows: 0fr; transition: grid-template-rows .42s cubic-bezier(.2,.8,.2,1); }
.guide-panel.open { grid-template-rows: 1fr; }
.guide-inner { overflow: hidden; min-height: 0; }
.guide-body { display: grid; grid-template-columns: 260px minmax(0,1fr); gap: 18px; padding: 4px 14px 14px; border-top: 1px solid #e2eef7; opacity: 0; transform: translateY(-6px); transition: opacity .3s ease .08s, transform .35s ease .08s; }
.guide-panel.open .guide-body { opacity: 1; transform: none; }
.guide-art { align-self: start; margin-top: 10px; padding: 8px; border-radius: 10px; background: #fff; border: 1px solid #e2e8f0; }
.guide-art svg { display: block; width: 100%; height: auto; overflow: visible; }
.guide-text { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 14px; }
.guide-block h4 { margin: 10px 0 5px; font-size: 12px; color: #0173B2; }
.guide-block p, .guide-block li { font-size: 12px; line-height: 1.5; color: #334155; text-align: left; }
.guide-block p { margin: 0; }
.guide-block ul { margin: 0; padding-left: 16px; display: grid; gap: 4px; }
.guide-panel.open .guide-block li, .guide-panel.open .guide-block p { animation: guideText .45s ease both; animation-delay: calc(var(--i,0) * 70ms + 160ms); }
.guide-extra { padding: 0 14px 14px; }
.guide-columns-title { font-size: 12px; font-weight: 750; color: #0173B2; margin: 2px 0 6px; }
.guide-extra .quality-guide-grid { border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
@keyframes guideText { from { opacity: 0; transform: translateX(-8px); } to { opacity: 1; transform: none; } }
.guide-art svg * { transform-box: fill-box; transform-origin: center; }
.guide-panel.open .g-pop { animation: gPop .45s cubic-bezier(.2,.9,.3,1.3) both; animation-delay: var(--d,0ms); }
.guide-panel.open .g-fade { animation: gFade .5s ease both; animation-delay: var(--d,0ms); }
.guide-panel.open .g-grow { transform-origin: bottom; animation: gGrow .6s cubic-bezier(.2,.8,.2,1) both; animation-delay: var(--d,0ms); }
.guide-panel.open .g-growx { transform-origin: left; animation: gGrowX .6s cubic-bezier(.2,.8,.2,1) both; animation-delay: var(--d,0ms); }
.guide-panel.open .g-slide { animation: gSlide .7s cubic-bezier(.2,.8,.2,1) both; animation-delay: var(--d,0ms); }
.guide-panel.open .g-ring { animation: gRing 1.8s ease-in-out 1.1s infinite both; }
.guide-panel.open .g-ring.g-late { animation-delay: 1.9s; }
.guide-panel.open .g-sweep-y { animation: gSweepY 3.2s ease-in-out .9s infinite both; }
.guide-panel.open .g-sweep-x { animation: gSweepX 3.6s ease-in-out .9s infinite both; }
.guide-panel.open .g-draw { animation: gDraw 1.2s ease 1s both; }
@keyframes gPop { from { opacity: 0; transform: scale(.4); } to { opacity: 1; transform: none; } }
@keyframes gFade { from { opacity: 0; } to { opacity: 1; } }
@keyframes gGrow { from { transform: scaleY(0); } to { transform: none; } }
@keyframes gGrowX { from { transform: scaleX(0); } to { transform: none; } }
@keyframes gSlide { from { opacity: 0; transform: translateX(var(--from,-60px)); } to { opacity: 1; transform: none; } }
@keyframes gRing { 0%,100% { opacity: .15; } 50% { opacity: 1; } }
@keyframes gSweepY { 0%,100% { transform: translateY(0); } 50% { transform: translateY(72px); } }
@keyframes gSweepX { 0%,100% { transform: translateX(0); } 50% { transform: translateX(162px); } }
@keyframes gDraw { from { stroke-dashoffset: 160; } to { stroke-dashoffset: 0; } }
@media (max-width: 1100px) { .guide-body { grid-template-columns: 1fr; } .guide-art { max-width: 300px; } .guide-text { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { .guide-panel, .guide-body, .guide-chevron, .guide-icon { transition: none !important; } .guide-panel * { animation: none !important; } }
.composition-controls label.inline-check { display: inline-flex; align-items: center; gap: 6px; font-weight: 650; cursor: pointer; }
.composition-controls label.inline-check input { accent-color: var(--brand); width: 15px; height: 15px; margin: 0; }
.rscu-legend .hatch-swatch { background: repeating-linear-gradient(135deg,#f1f5f9 0 3px,#94a3b8 3px 4px); }
#compositionTable tr.ref-row td { background: #f1f5f9 !important; color: #475569; font-style: normal; }
#compositionTable tr.ref-row td:first-child { white-space: nowrap; }
.ref-badge { display: inline-block; padding: 0 6px; margin-right: 6px; border-radius: 5px; background: #475569; color: #fff; font-size: 10px; font-weight: 750; letter-spacing: .02em; }
.marker-heatmap-scroll svg { display: block; width: auto; max-width: none; }
#referenceGenes svg, #compositionStrip svg { max-width: 100%; }
/* Quality per assembly: same header, row height and font as the other tables. */
#qualityTable { font-size: 13px; }
#qualityTable th, #qualityTable td { padding: 8px 10px; }
#qualityTable thead tr.group-head th { top: 0; height: 30px; background: #e2e8f0; color: #334155; text-align: center; border-left: 1px solid #f8fafc; border-bottom: 1px solid #cbd5e1; font-size: 10.5px; letter-spacing: .06em; }
#qualityTable thead tr.column-head th { top: 30px; text-transform: uppercase; letter-spacing: .035em; font-size: 11px; white-space: nowrap; line-height: 1.2; vertical-align: middle; border-left: 1px solid #f1f5f9; color: #475569; }
#qualityTable thead tr.column-head th.q-sticky { min-width: 0; }
#qualityTable .q-sub { display: inline; margin-left: 4px; font-size: 11px; }
#qualityTable td.q-ok, #qualityTable td.q-warn, #qualityTable td.q-bad { font-weight: 650; }
#qualityTable tr.q-project td { background: #e8f3f9 !important; font-size: 13px; border-top: 12px solid var(--bg); padding: 7px 10px; }
#qualityTable td.q-alerts { white-space: nowrap; min-width: 0; max-width: none; }
#qualityTable td.q-alerts .alert-chip { white-space: nowrap; }
.alert-chip.more { border-style: dashed; color: #475569; background: #f8fafc; cursor: help; }
</style>
</head>
<body>
<div class="layout">
  <aside id="sidebar" class="sidebar" aria-label="Report filters and sections">
    <div class="sidebar-logo">__LOGO_HTML__</div>
    <div class="sidebar-block">
      <div class="sidebar-heading">Filters</div>
      <div class="side-filters">
        <div><span class="filter-label">Seed <span class="info-dot" data-tooltip="Select one or more seed inputs. Use the search box inside the menu when many seeds are available.">i</span></span><div id="seedFilter" class="multi-select"></div></div>
        <div><span class="filter-label">K-mer <span class="info-dot" data-tooltip="Select one or more K-mer values. Multiple values can be compared simultaneously.">i</span></span><div id="kmerFilter" class="multi-select"></div></div>
        <div><span class="filter-label">Assembly status <span class="info-dot" data-tooltip="Choose circularized, non-circularized, or both assembly states.">i</span></span><div id="statusFilter" class="multi-select"></div></div>
        <div><span class="filter-label">Tandem repeats <span class="info-dot" data-tooltip="Filter runs according to whether TRF detected tandem repeats.">i</span></span><div id="repeatFilter" class="multi-select"></div></div>
        <button id="resetFilters" class="reset">Reset filters</button>
      </div>
      <div id="filterSummary" class="filter-summary"></div>
    </div>
  </aside>

<main class="shell">
  <div id="errorBox"></div>

  <header>
    <div class="header-text">
      <div class="eyebrow">moCURA</div>
      <h1>__REPORT_TITLE__</h1>
      <div class="subtitle">Interactive organelle assembly report.</div>
    </div>
    <div class="project-picker">
      <button id="projectPickerToggle" class="project-notice" type="button" aria-expanded="false" aria-controls="projectPickerPanel">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true"><path d="M3 5h18M6 12h12M10 19h4"></path></svg>
        <span id="projectNoticeText"></span>
        <span class="project-notice-action">Choose projects</span>
      </button>
      <div id="projectPickerPanel" class="project-picker-panel" hidden>
        <div class="project-picker-tools">
          <div class="table-search-wrap">
            <svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path></svg>
            <input id="projectPickerSearch" type="search" placeholder="Search project, species or location...">
          </div>
          <button type="button" class="picker-action" data-picker="all">Select all</button>
          <button type="button" class="picker-action" data-picker="visible">Select matches</button>
          <button type="button" class="picker-action" data-picker="clear">Clear</button>
        </div>
        <div id="projectPickerList" class="project-picker-list"></div>
        <div class="project-picker-foot">
          <span id="projectPickerCount" class="table-count"></span>
          <span class="project-picker-buttons"><button type="button" class="picker-action" data-picker="cancel">Cancel</button><button type="button" class="picker-apply" data-picker="apply">Show selected projects</button></span>
        </div>
      </div>
    </div>
    <div id="projectTabs" class="tabs"></div>
  </header>

  <div id="sectionBar" class="section-bar">
    <nav class="nav" aria-label="Report sections">
      <a class="nav-link" href="#recommendation" data-tooltip="Recommended assembly per sample and the full ranking with the score breakdown.">Recommendation</a>
      <a class="nav-link active" href="#overview" data-tooltip="Summary cards and guidance for the current filtered view.">Overview</a>
      <a class="nav-link" href="#assemblies" data-tooltip="Linked NOVOPlasty assembly metrics. Hovering one run highlights the same run in all four panels.">Assemblies</a>
      <a class="nav-link" href="#pilon" data-tooltip="Interactive polishing metrics from Pilon.">Pilon</a>
      <a class="nav-link" href="#genome" data-tooltip="Marker and tandem-repeat positions for every assembly that passes the filters.">Genome</a>
      <a class="nav-link" href="#quality" data-tooltip="Gene completeness, coverage, junction support, annotation integrity, concordance, heteroplasmy and NCBI validation.">Quality</a>
      <a class="nav-link" href="#species" data-tooltip="Species identification against BOLD and GenBank, and comparison with RefSeq genomes of the same genus or family.">Species</a>
      <a class="nav-link" href="#composition" data-tooltip="GC content, skews and codon usage (RSCU), compared with the RefSeq genomes.">Composition</a>
      <a class="nav-link" href="#markers" data-tooltip="Marker lengths per assembly, colored by the difference from the most common length in the sample, with the RefSeq median.">Markers</a>
      <a class="nav-link" href="#repeats" data-tooltip="TRF repeat families, genomic context and comparative table.">Repeats</a>
      <a class="nav-link" href="#snps" data-tooltip="True-SNP matrices rendered directly with D3 in a Snipit-like layout.">SNPs</a>
      <a class="nav-link" href="#map" data-tooltip="Sampling localities with SNP differences on the embedded geographic basemap.">Map</a>
      <a class="nav-link" href="#provenance" data-tooltip="Run time, versions, arguments and configuration used to build this report.">Provenance</a>
    </nav>
    <label class="species-toggle" data-tooltip-html="When enabled, species labels are shortened from <em>Homo sapiens</em> to <em>H. sapiens</em> throughout the report. It is disabled by default."><input id="abbreviateSpecies" type="checkbox"> Abbreviate species <span class="info-dot">i</span></label>
  </div>

  <section id="recommendation" class="section">
    <h2>Recommendation <span class="info-dot" data-tooltip="A transparent weighted score combines annotation completeness, integrity alerts, junction support, coverage uniformity, Pilon confirmed bases, membership of the majority concordance group and closeness to the modal genome length. Only circularized assemblies can be recommended. Nothing is discarded.">i</span></h2>
    <div id="recommendationSubtitle" class="section-note"></div>
    <div class="guide-slot" data-guide="recommendation"></div>
    <div class="card paths-card">
      <div class="paths-head">
        <div class="chart-title">Files of the recommended assemblies <span class="info-dot" data-tooltip="Absolute paths of the files of the recommended assembly of every project in the current filters, one per line, ready to paste into a terminal (for example after cp or scp). Pilon FASTA is the polished sequence; the rotated GenBank starts at rrnS.">i</span></div>
        <div class="paths-options" role="radiogroup" aria-label="File type">
          <label><input type="radio" name="pathKind" value="Pilon FASTA" checked> Pilon FASTA</label>
          <label><input type="radio" name="pathKind" value="Rotated GenBank"> Rotated GenBank</label>
          <label><input type="radio" name="pathKind" value="GenBank"> GenBank</label>
          <label><input type="radio" name="pathKind" value="all"> All files</label>
        </div>
        <button id="copyRecommendedPaths" class="copy-button" type="button"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"></rect><path d="M5 15V5a2 2 0 0 1 2-2h10"></path></svg><span>Copy paths</span></button>
      </div>
      <textarea id="recommendedPaths" readonly spellcheck="false" aria-label="Paths of the recommended assemblies"></textarea>
      <div id="recommendedPathsNote" class="paths-note"></div>
    </div>
    <details id="recommendationDetails" class="card reco-details">
      <summary>Recommended assembly per sample <span id="recommendationCount" class="summary-count"></span></summary>
      <div id="recommendationCards" class="recommendation-grid"></div>
    </details>
    <details class="card table-card ranking-details">
      <summary>Full ranking and score breakdown <span id="rankingCount" class="summary-count"></span></summary>
      <div id="rankingWeights" class="ranking-weights"></div>
      <div class="table-scroll"><table id="rankingTable" class="assembly-table ranking-table"><thead id="rankingHead"></thead><tbody id="rankingBody"></tbody></table></div>
    </details>
  </section>

  <section id="overview" class="section">
    <div class="metrics">
      <div class="card metric"><div class="metric-label">Projects <span class="info-dot" data-tooltip="Number of projects represented after applying the current filters.">i</span></div><div id="metricProjects" class="metric-value"></div></div>
      <div class="card metric"><div class="metric-label">Runs <span class="info-dot" data-tooltip="Number of NOVOPlasty project, seed and K-mer combinations in the current view.">i</span></div><div id="metricAssemblies" class="metric-value"></div></div>
      <div class="card metric"><div class="metric-label">Circularized <span class="info-dot" data-tooltip="Runs reported as circularized by the assembly workflow.">i</span></div><div id="metricCircularized" class="metric-value"></div></div>
      <div class="card metric"><div class="metric-label">Rotated genomes <span class="info-dot" data-tooltip="Rotated GenBank assemblies available for marker and genome-position analyses.">i</span></div><div id="metricGenbanks" class="metric-value"></div></div>
      <div class="card metric"><div class="metric-label">TRF repeats <span class="info-dot" data-tooltip="Number of tandem-repeat records detected by TRF in the filtered assemblies.">i</span></div><div id="metricRepeats" class="metric-value"></div></div>
      <div class="card metric"><div class="metric-label">Median coverage <span class="info-dot" data-tooltip="Median NOVOPlasty average organelle coverage for the filtered runs.">i</span></div><div id="metricCoverage" class="metric-value"></div></div>
    </div>
    <div id="readQcPanel" class="read-qc-panel"></div>
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
    <div class="guide-slot" data-guide="assemblyPanels"></div>
    <div class="assembly-metric-grid">
      <div class="card assembly-metric-card"><div class="chart-title">Total contigs</div><div class="chart-subtitle">Number of contigs recovered for each project, seed and K-mer combination.</div><div id="metricTotalContigs" class="assembly-metric-chart"></div></div>
      <div class="card assembly-metric-card"><div class="chart-title">Largest contig</div><div class="chart-subtitle">Largest assembled contig relative to the configured organelle genome range.</div><div id="metricLargestContig" class="assembly-metric-chart"></div></div>
      <div class="card assembly-metric-card"><div class="chart-title">Smallest contig</div><div class="chart-subtitle">Smallest assembled contig relative to the configured organelle genome range.</div><div id="metricSmallestContig" class="assembly-metric-chart"></div></div>
      <div class="card assembly-metric-card"><div class="chart-title">Average organelle coverage</div><div class="chart-subtitle">Average organelle coverage reported by NOVOPlasty.</div><div id="metricAverageCoverage" class="assembly-metric-chart"></div></div>
    </div>

    <div class="card table-card" data-guide="assemblyTable">
      <div class="table-toolbar">
        <div><div class="table-title">Assembly data</div><div id="assemblyTableCount" class="table-count"></div></div>
        <div class="table-tools">
          <div class="table-search-control">
            <span class="filter-label">Search table <span class="info-dot" data-tooltip="Filters Assembly data across project/species, location, seed, K-mer, status and numeric fields. It does not change the plots above.">i</span></span>
            <div class="table-search-wrap">
              <svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path></svg>
              <input id="assemblySearch" type="search" placeholder="Search project, species, location, seed, K-mer or value...">
            </div>
            <div class="assembly-table-help"><svg viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M8 7h8M8 17h8M5 12h14"></path><path d="m8 9-3 3 3 3M16 9l3 3-3 3"></path></svg><span>Hold the right mouse button and drag to scroll the table.</span></div>
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
      <div class="card chart-card" data-guide="pilonMetrics"><div class="chart-title">Pilon metrics</div><div class="chart-subtitle">One row per project (per seed when a single project is selected), with the median of its runs. Every column has its own unit and its own colour scale, from the lowest to the highest value in that column; the range is written under each title.</div><label class="heatmap-toggle"><input id="pilonShowValues" type="checkbox"> Show values in the cells</label><div id="pilonMetricsHeatmap" class="chart" style="min-height:0"></div></div>
      <div class="card chart-card" data-guide="pilonBeforeAfter"><div class="chart-title">Genome length before and after Pilon</div><div class="chart-subtitle">Median comparison.</div><div id="pilonBeforeAfterChart" class="chart"></div></div>
    </div>
    <div class="card chart-card" data-guide="pilonCorrections" style="margin-top:16px"><div class="chart-title">Pilon corrections</div><div class="chart-subtitle">SNPs, insertions and deletions.</div><div id="pilonCorrectionsChart" class="chart"></div></div>
  </section>

  <section id="genome" class="section">
    <h2>Genome structure and tandem-repeat positions <span class="info-dot" data-tooltip="Every filtered rotated assembly is drawn as a separate genomic track. Colored blocks are annotated markers and orange blocks are TRF tandem repeats.">i</span></h2>
    <div class="section-note">Assemblies are grouped by identical Seed + K-mer combinations. Within each group, projects share the same coordinate scale, gene colors and repeat-family colors so differences are easy to compare. The consensus sequence of every tandem repeat is written next to its block and listed under the assembly name.</div>
    <div class="genome-legend"><span><i style="background:#0173B2"></i>Genes on the + strand (top line) and − strand (second line)</span><span><i style="background:#DE8F05"></i>TRF tandem repeat, labelled with its consensus sequence. "Repeat 1: 70 bp = 35.5 copies of 2 bp" reads as a 70 bp array made of 35.5 copies of a 2 bp unit</span><span><svg width="12" height="10" aria-hidden="true"><path d="M1,1 h10 l-5,8 z" fill="#D55E00"></path></svg>Pilon correction</span><span><i style="background:rgba(1,115,178,.35)"></i>Read depth</span><span><i style="background:rgba(213,94,0,.25)"></i>Unresolved Pilon break</span></div>
    <div class="guide-slot" data-guide="genome"></div>
    <div class="card chart-card genome-scroll" style="margin-top:10px"><div id="genomeTimeline" class="chart"></div></div>
  </section>

  <section id="quality" class="section">
    <h2>Assembly quality <span class="info-dot" data-tooltip="Read directly from the OrganPipe outputs: MITOS2 gene annotation, samtools depth, BLAST read recruitment, Pilon change lists and nhmmer intergenic searches.">i</span></h2>
    <div id="qualitySubtitle" class="section-note"></div>
    <div class="quality-note">Coverage and read recruitment come from the reads NOVOPlasty used to build each assembly (<code>Assembled_reads</code>). They tend to agree with the assembly by construction, so they flag problems but do not independently validate it.</div>
    <div class="card chart-card" data-guide="completeness">
      <div class="chart-title">Gene completeness <span class="info-dot" data-tooltip="Each row is one assembly, each column one of the 37 mitochondrial genes annotated by MITOS2. Partial at origin marks genes kept only as a fragment because they cross the contig origin.">i</span></div>
      <div class="chart-subtitle">37 genes from MITOS2: present, absent, duplicated or kept only as a fragment at the contig origin. Assemblies are grouped by project, then by Seed + K-mer (shaded blocks); the rows of a block are its assembly copies. The last column compares the gene order with the most common order in the project.</div>
      <div class="completeness-scroll"><div id="completenessHeatmap" class="chart"></div></div>
    </div>
    <div class="card table-card" data-guide="quality" style="margin-top:16px">
      <div class="table-toolbar">
        <div><div class="table-title">Quality per assembly <span class="info-dot" data-tooltip="One row per assembly copy, grouped by project. Hover a column title for its definition, or open How to read this for every column.">i</span></div><div id="qualityTableCount" class="table-count"></div></div>
        <div class="table-tools">
          <div class="table-search-control">
            <div class="table-search-wrap">
              <svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path></svg>
              <input id="qualitySearch" type="search" placeholder="Search project, seed, K-mer or alert...">
            </div>
          </div>
          <label class="quality-only-alerts"><input id="qualityOnlyAlerts" type="checkbox"> Only assemblies with alerts</label>
        </div>
      </div>
      <div class="quality-legend"><span><i style="background:#e7f6ef;border:1px solid #9fd8c0"></i>Within the expected range</span><span><i style="background:#fff4e0;border:1px solid #f5c26b"></i>Worth checking</span><span><i style="background:#fde8e4;border:1px solid #f0a28f"></i>Problem</span><span>Uncoloured cells have no fixed threshold; compare them across rows.</span></div>
      <div id="qualityTableScroll" class="table-scroll"><table id="qualityTable" class="assembly-table"><thead id="qualityTableHead"></thead><tbody id="qualityTableBody"></tbody></table></div>
    </div>
    <div class="card table-card" data-guide="integrity" style="margin-top:16px">
      <div class="table-toolbar">
        <div><div class="table-title">Annotation integrity <span class="info-dot" data-tooltip="Checks of every annotated gene in the rotated GenBank: internal stop codons, frame, start and stop codons, genes crossing the origin and lengths far from the project mode.">i</span></div><div id="integrityCount" class="table-count"></div></div>
        <div class="table-tools">
          <div class="table-search-control"><div class="table-search-wrap"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path></svg><input id="integritySearch" type="search" placeholder="Search assembly, gene or check..."></div></div>
          <label class="quality-only-alerts"><input id="integrityShowInfo" type="checkbox"> Show informative checks (incomplete stop codons)</label>
        </div>
      </div>
      <div class="table-scroll" style="max-height:460px"><table id="integrityTable" class="assembly-table"><thead id="integrityHead"></thead><tbody id="integrityBody"></tbody></table></div>
    </div>
    <div class="card chart-card" data-guide="concordance" style="margin-top:16px">
      <div class="chart-title">Concordance among assemblies of the same sample <span class="info-dot" data-tooltip="Rotated genomes of each project aligned with MAFFT. Identity excludes gap columns; coverage is the share of the longer genome compared. Linked assemblies (identity and coverage above the thresholds) form groups; the largest is the majority group.">i</span></div>
      <div id="concordanceSubtitle" class="chart-subtitle"></div>
      <div id="concordanceGrid" class="concordance-grid"></div>
    </div>
    <div class="card table-card" data-guide="heteroplasmy" style="margin-top:16px">
      <div class="table-toolbar">
        <div><div class="table-title">Heteroplasmy candidates <span class="info-dot" data-tooltip="Sites where a second base is present in the reads of the rotated BAM. High confidence: depth, minor reads and frequency above the thresholds, minor base on both strands, away from the contig ends, outside tandem repeats and not in a cluster of candidate sites. Frequencies are a lower bound because the BAM holds the reads NOVOPlasty assembled; a NUMT or contamination gives the same signal.">i</span></div><div id="heteroplasmyCount" class="table-count"></div></div>
        <div class="table-tools">
          <div class="table-search-control"><div class="table-search-wrap"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path></svg><input id="heteroplasmySearch" type="search" placeholder="Search project, gene or position..."></div></div>
          <label class="quality-only-alerts"><input id="heteroplasmyShowLow" type="checkbox"> Show low-confidence sites</label>
        </div>
      </div>
      <div class="table-scroll" style="max-height:460px"><table id="heteroplasmyTable" class="assembly-table"><thead id="heteroplasmyHead"></thead><tbody id="heteroplasmyBody"></tbody></table></div>
    </div>
    <div class="card table-card" data-guide="validation" style="margin-top:16px">
      <div class="table-toolbar">
        <div><div class="table-title">NCBI submission check (table2asn) <span class="info-dot" data-tooltip="The GenBank of each checked assembly is converted into a submission (feature table with NCBI product names, incomplete stop codons completed by polyadenylation) and validated with table2asn. Rejects, errors and FATAL discrepancies would block or delay a GenBank submission. The .sqn, .tbl, .fsa and .gbf files are in the folder shown.">i</span></div><div id="validationCount" class="table-count"></div></div>
      </div>
      <div class="table-scroll" style="max-height:420px"><table id="validationTable" class="assembly-table"><thead id="validationHead"></thead><tbody id="validationBody"></tbody></table></div>
      <details class="quality-guide" id="validationMessagesDetails">
        <summary id="validationMessagesSummary">Messages</summary>
        <div class="table-scroll" style="max-height:420px"><table id="validationMessagesTable" class="assembly-table"><thead id="validationMessagesHead"></thead><tbody id="validationMessagesBody"></tbody></table></div>
      </details>
    </div>
  </section>

  <section id="species" class="section">
    <h2>Species identification and RefSeq references <span class="info-dot" data-tooltip="The barcode of one assembly per sample (COI for mitochondria, rbcL and matK for chloroplasts) is searched in BOLD and GenBank. The taxonomy of the declared species, or of the best match, then selects RefSeq genomes of the same genus (or family) to compare genome length, gene lengths and tandem repeats.">i</span></h2>
    <div id="speciesSubtitle" class="section-note"></div>
    <div class="card table-card" data-guide="species" style="margin-top:12px">
      <div class="table-toolbar"><div><div class="table-title">Species identification <span class="info-dot" data-tooltip="Species are ranked by their best identity among hits overlapping at least the minimum length (bit score favours long partial genomes over barcodes). With metadata: Confirmed when the declared species is at or above the identity threshold and no other species is clearly closer; Ambiguous when another species is closer; Not confirmed below the threshold; No reference when neither database has the declared species. Without metadata the most similar species of each database are listed.">i</span></div><div id="speciesCount" class="table-count"></div></div></div>
      <div class="table-scroll"><table id="speciesTable" class="assembly-table species-table"><thead id="speciesHead"></thead><tbody id="speciesBody"></tbody></table></div>
    </div>
    <div class="card chart-card" data-guide="referenceStrip" style="margin-top:16px">
      <div class="chart-title">Assemblies against the RefSeq genomes <span class="info-dot" data-tooltip="One row per sample. Grey diamonds are RefSeq genomes of the genus (or family) of the sample; the green band is their range widened by the tolerance in config.yml. Circles are the assemblies in view, green inside the band and orange outside; the outlined circle is the recommended assembly. For genome length the scale spans 15% around the references: assemblies beyond it (partial contigs) are triangles at the edge, with their length in the tooltip.">i</span></div>
      <div id="referenceSubtitle" class="chart-subtitle"></div>
      <div class="composition-controls">
        <label for="referenceMetric">Compare</label>
        <select id="referenceMetric"><option value="length">Genome length (bp)</option><option value="repeats">Bases in tandem repeats (TRF)</option></select>
      </div>
      <div class="rscu-scroll"><div id="referenceStrip" class="chart" style="min-height:0"></div></div>
    </div>
    <div class="card chart-card" data-guide="referenceGenes" style="margin-top:16px">
      <div class="chart-title">Gene lengths against the RefSeq genomes <span class="info-dot" data-tooltip="One row per gene, on the same layout as the genome-length chart: diamonds are the RefSeq genomes, the green band is their range widened by the gene tolerance, circles are the assemblies. The axis is the difference from the median length of the gene in the references.">i</span></div>
      <div id="referenceGenesSubtitle" class="chart-subtitle"></div>
      <div class="composition-controls">
        <label for="referenceGenesScope">Assemblies</label>
        <select id="referenceGenesScope"><option value="recommended">Recommended assembly of each sample</option><option value="all">Every assembly in view</option></select>
        <label class="inline-check"><input id="referenceGenesOutside" type="checkbox"> Only genes outside the reference range</label>
      </div>
      <div id="referenceGenesLegend" class="rscu-legend"></div>
      <div class="rscu-scroll"><div id="referenceGenes" class="chart" style="min-height:0"></div></div>
    </div>
    <details class="card quality-guide" style="margin-top:16px" id="referenceListDetails">
      <summary id="referenceListSummary">RefSeq genomes used</summary>
      <div class="table-scroll" style="max-height:420px"><table id="referenceListTable" class="assembly-table"><thead id="referenceListHead"></thead><tbody id="referenceListBody"></tbody></table></div>
    </details>
  </section>

  <section id="composition" class="section">
    <h2>Sequence composition <span class="info-dot" data-tooltip="GC content and AT/GC skews of the whole genome and of the protein-coding genes by strand, and the relative synonymous codon usage (RSCU) of the protein-coding genes.">i</span></h2>
    <div id="compositionSubtitle" class="section-note"></div>
    <div id="compositionStripCard" class="card chart-card" data-guide="compositionStrip" style="margin-top:12px">
      <div class="chart-title">Composition against the RefSeq genomes <span class="info-dot" data-tooltip="Base composition of the assemblies of each sample and of the RefSeq genomes compared with it (same genus, or family). Diamonds: RefSeq genomes; green band: their range; circles: assemblies, outlined when recommended.">i</span></div>
      <div id="compositionStripSubtitle" class="chart-subtitle"></div>
      <div class="composition-controls">
        <label for="compositionMetric">Compare</label>
        <select id="compositionMetric"></select>
        <label for="compositionScope">Assemblies</label>
        <select id="compositionScope"><option value="recommended">Recommended assembly of each sample</option><option value="all">Every assembly in view (partial contigs included)</option></select>
      </div>
      <div class="rscu-scroll"><div id="compositionStrip" class="chart" style="min-height:0"></div></div>
    </div>
    <div class="card chart-card" data-guide="rscu" style="margin-top:16px">
      <div class="chart-title">Relative synonymous codon usage</div>
      <div class="chart-subtitle">RSCU = observed count / mean count of the synonymous codons of that amino acid. 1 means no preference; above 1, the codon is used more than its synonyms. Terminal stop codons and incomplete codons are left out. Amino acids with six codons are split into their two codon boxes (for example Leu CTN and Leu TTR).</div>
      <div class="composition-controls">
        <label for="rscuView">View</label>
        <select id="rscuView"><option value="stacked">One assembly: stacked bars per amino acid</option><option value="heatmap">Compare assemblies: heatmap of every codon</option></select>
        <label for="rscuSelect" id="rscuSelectLabel">Assembly</label><select id="rscuSelect"></select>
      </div>
      <div id="rscuLegend" class="rscu-legend"></div>
      <div class="rscu-scroll"><div id="rscuChart" class="chart" style="min-height:0"></div></div>
    </div>
    <div class="card table-card" data-guide="compositionTable">
      <div class="table-toolbar"><div><div class="table-title">Composition per assembly</div><div id="compositionCount" class="table-count"></div></div></div>
      <div class="table-scroll"><table id="compositionTable" class="assembly-table"><thead id="compositionHead"></thead><tbody id="compositionBody"></tbody></table></div>
    </div>
  </section>

  <section id="markers" class="section">
    <h2>Marker comparison <span class="info-dot" data-tooltip="Length of every annotated marker in every assembly, compared with the most common length of the same marker in the sample (the mode) and with the median of the RefSeq genomes.">i</span></h2>
    <div class="section-note">Cells keep their length in bp; the colour shows how far it is from the mode of the sample, so the assemblies and markers that disagree stand out.</div>
    <div class="card chart-card marker-heatmap-card" data-guide="markers">
      <div class="chart-title">Marker lengths against the mode of each sample</div>
      <div id="markerSubtitle" class="chart-subtitle"></div>
      <div class="marker-category-controls" aria-label="Marker class">
        <label class="marker-category-option"><input class="marker-category-checkbox" type="checkbox" value="PCGs" checked> PCGs</label>
        <label class="marker-category-option"><input class="marker-category-checkbox" type="checkbox" value="rRNAs"> rRNAs</label>
        <label class="marker-category-option"><input class="marker-category-checkbox" type="checkbox" value="tRNAs"> tRNAs</label>
        <label class="marker-category-option"><input class="marker-category-checkbox" type="checkbox" value="All"> All markers</label>
      </div>
      <div class="composition-controls">
        <label for="markerValueMode">Cells show</label>
        <select id="markerValueMode"><option value="length">Length (bp)</option><option value="difference">Difference from the mode (bp)</option></select>
        <label class="inline-check"><input id="markerOnlyDifferent" type="checkbox"> Only assemblies that differ from the mode</label>
      </div>
      <div id="markerLegend" class="rscu-legend"></div>
      <div class="marker-heatmap-scroll"><div id="markerLengthHeatmap" class="chart" style="min-height:0"></div></div>
    </div>
  </section>

  <section id="repeats" class="section">
    <h2>Tandem repeats <span class="info-dot" data-tooltip="Comparative TRF repeat table with proportional in-cell bars, project/species metadata, location, gene context and consensus.">i</span></h2>
    <div id="repeatSubtitle" class="section-note"></div>
    <div class="card table-card" data-guide="repeats">
      <div class="table-toolbar">
        <div><div class="table-title">Comparative repeat table</div><div id="repeatTableCount" class="table-count"></div></div>
        <div class="table-tools">
          <div class="table-search-control">
            <span class="filter-label">Search table <span class="info-dot" data-tooltip="Searches project/species, location, seed, K-mer, repeat metrics, gene context and consensus sequence. It does not change the plots outside this table.">i</span></span>
            <div class="table-search-wrap">
              <svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path></svg>
              <input id="repeatSearch" type="search" placeholder="Search project, species, location, seed, K-mer or repeat value...">
            </div>
            <div class="assembly-table-help"><svg viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M8 7h8M8 17h8M5 12h14"></path><path d="m8 9-3 3 3 3M16 9l3 3-3 3"></path></svg><span>Hold the right mouse button and drag to scroll the table.</span></div>
          </div>
        </div>
      </div>
      <div id="repeatTableScroll" class="table-scroll"><table id="repeatTable" class="repeat-table assembly-table resizable-table"><thead><tr id="repeatTableHead"></tr></thead><tbody id="repeatTableBody"></tbody></table></div>
    </div>
  </section>

  <section id="snps" class="section">
    <h2>Marker SNPs <span class="info-dot" data-tooltip="Only true SNP positions are shown. Each nucleotide state is drawn directly with D3 from the SNP matrix table.">i</span></h2>
    <div id="snpSubtitle" class="section-note"></div>
    <div class="guide-slot" data-guide="snps"></div>
    <div class="snp-toolbar">
      <label><input id="snpIncludeIncomplete" type="checkbox"> Include incomplete or non-circularized sequences</label>
      <span id="snpToolbarNote"></span>
    </div>
    <div id="snpGallery" class="snp-grid"></div>
  </section>

  <section id="map" class="section">
    <h2>Sampling map <span class="info-dot" data-tooltip="Sampling localities are integrated with the current SNP matrices. Choose which markers contribute to the map statistics and optionally display a haplotype network.">i</span></h2>
    <div id="mapSubtitle" class="section-note">Sampling localities are filtered together with Marker SNPs. Hover or click a point to inspect the exact markers carrying differences.</div>
    <div class="guide-slot" data-guide="map"></div>
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

  <details id="provenance" class="section provenance-section">
    <summary>Provenance</summary>
    <div class="section-note">How this report was produced: run time and memory, versions, arguments, effective configuration and OrganPipe benchmarks.</div>
    <div id="provenanceBody"></div>
  </details>

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
</main>
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
  N: '#E5E7EB',
  '·': '#ffffff'
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
function num(value, fallback = null) { if (value === null || value === undefined || (typeof value === 'string' && value.trim() === '')) return fallback; const n = Number(value); return Number.isFinite(n) ? n : fallback; }
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
  const value=text(row['Location'] ?? row.location).trim();
  // Without metadata, Location of the marker table is a feature location such as [14405:14475](-).
  return /^\[\d+:\d+\]/.test(value)?'':value;
}

function tableColumnLabel(column) {
  if(column==='Project name')return 'Project / Species';
  if(column==='Gene context label')return 'Gene context';
  return column;
}

function formatNumericMetric(column, numeric) {
  if (numeric === null) return '—';
  if (column === 'Integrity alerts') return d3.format(',d')(numeric);
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
  const tip=cursorTooltip();
  if(tip){
    cursorPoint={x:event.clientX,y:event.clientY};
    if(html!==cursorHtml){ cursorHtml=html; tip.setContent(html); }
    if(!tip.state.isVisible)tip.show();
    else if(tip.popperInstance)tip.popperInstance.update();
    return;
  }
  tooltip.innerHTML = html;
  tooltip.style.opacity = 1;
  tooltip.style.left = `${Math.min(window.innerWidth - 350, event.clientX + 14)}px`;
  tooltip.style.top = `${Math.min(window.innerHeight - 140, event.clientY + 14)}px`;
}
function unhover() { if(cursorTip)cursorTip.hide(); tooltip.style.opacity = 0; }

let projectPickerDraft=new Set();

function projectRunCount(project) {
  return REPORT.summary.filter(row=>text(row['Project name'])===text(project)).length;
}

function projectSearchText(project) {
  const record=projectRecord(project);
  return [project,record['Species'],locationText(record)].map(text).join(' ').toLowerCase();
}

function updateProjectNotice() {
  const total=REPORT.projects.length;
  const shown=state.projects.size;
  const notice=document.getElementById('projectNoticeText');
  if(!notice)return;
  notice.innerHTML=shown===total
    ? `<strong>Showing all ${total} project${total===1?'':'s'}.</strong> Click here to choose which projects you want to view.`
    : `<strong>Showing ${shown} of ${total} projects.</strong> Click here to change the selection.`;
}

function renderProjectPickerList() {
  const list=document.getElementById('projectPickerList');
  const query=text(document.getElementById('projectPickerSearch').value).trim().toLowerCase();
  const projects=REPORT.projects.map(text).filter(project=>!query||projectSearchText(project).includes(query));
  list.innerHTML=projects.length
    ? projects.map(project=>{
        const record=projectRecord(project);
        const runs=projectRunCount(project);
        return `<label class="multi-option"><input type="checkbox" value="${esc(project)}" ${projectPickerDraft.has(project)?'checked':''}><span>${projectDisplayHtml(record)}${locationText(record)?` <span class="table-count">· ${esc(locationText(record))}</span>`:''}</span><span class="option-meta">${runs} run${runs===1?'':'s'}</span></label>`;
      }).join('')
    : '<div class="multi-empty">No project matches the search.</div>';
  list.querySelectorAll('input[type="checkbox"]').forEach(input=>input.addEventListener('change',()=>{
    if(input.checked)projectPickerDraft.add(input.value);else projectPickerDraft.delete(input.value);
    updateProjectPickerCount();
  }));
  updateProjectPickerCount();
}

function updateProjectPickerCount() {
  document.getElementById('projectPickerCount').textContent=`${projectPickerDraft.size} of ${REPORT.projects.length} projects selected`;
  document.querySelector('[data-picker="apply"]').disabled=!projectPickerDraft.size;
}

function setProjectPickerOpen(open) {
  const panel=document.getElementById('projectPickerPanel');
  const toggle=document.getElementById('projectPickerToggle');
  panel.hidden=!open;
  toggle.setAttribute('aria-expanded',open?'true':'false');
  if(open){
    projectPickerDraft=new Set(state.projects);
    document.getElementById('projectPickerSearch').value='';
    renderProjectPickerList();
    setTimeout(()=>document.getElementById('projectPickerSearch').focus(),0);
  }
}

function applyProjectSelection(projects) {
  state.projects=new Set([...projects].map(text));
  state.assembly=null;
  document.getElementById('assemblySearch').value='';
  document.getElementById('repeatSearch').value='';
  renderTabs();
  resetFilterSelections();
  renderAll();
}

function initProjectPicker() {
  document.getElementById('projectPickerToggle').addEventListener('click',()=>setProjectPickerOpen(document.getElementById('projectPickerPanel').hidden));
  document.getElementById('projectPickerSearch').addEventListener('input',renderProjectPickerList);
  document.querySelectorAll('[data-picker]').forEach(button=>button.addEventListener('click',()=>{
    const action=button.dataset.picker;
    if(action==='all')REPORT.projects.forEach(project=>projectPickerDraft.add(text(project)));
    if(action==='clear')projectPickerDraft.clear();
    if(action==='visible'){
      const query=text(document.getElementById('projectPickerSearch').value).trim().toLowerCase();
      REPORT.projects.map(text).filter(project=>!query||projectSearchText(project).includes(query)).forEach(project=>projectPickerDraft.add(project));
    }
    if(action==='cancel'){setProjectPickerOpen(false);return;}
    if(action==='apply'){
      if(!projectPickerDraft.size)return;
      setProjectPickerOpen(false);
      applyProjectSelection(projectPickerDraft);
      return;
    }
    renderProjectPickerList();
  }));
}

function renderTabs() {
  updateProjectNotice();
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

function assemblyLabelWidth(width) {
  return Math.round(Math.min(250,Math.max(150,width*.46)));
}

function renderAssemblySpeciesLabels() {
  if(!document.getElementById('metricSpeciesLabels'))return;
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
  const width=Math.max(220,container.clientWidth||300);
  const rowHeight=40;
  const densityHeight=64;
  const showLabels=id==='metricTotalContigs';
  const labelWidth=showLabels?assemblyLabelWidth(width):0;
  const margin={top:densityHeight+18,right:14,bottom:46,left:showLabels?labelWidth+12:20};
  const height=Math.max(220,margin.top+projects.length*rowHeight+margin.bottom);

  const svg=d3.select('#'+id).append('svg').attr('viewBox',`0 0 ${width} ${height}`).attr('width',width).attr('height',height);
  const pointPadding=12;
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
    if(showLabels){
      const label=svg.append('text').attr('x',8).attr('y',y(project)+y.bandwidth()/2+4).attr('font-size',10.5).attr('fill','#475569');
      setSvgProjectLabel(label,projectRecord(project));
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
  ['pilonBeforeAfterChart','pilonCorrectionsChart'].forEach(id=>{
    const element=document.getElementById(id);
    if(element)element.style.minHeight=`${dynamicHeight}px`;
  });
}

let pilonShowValues=false;

function svgLabelWidth(labels,fontSize=10.5) {
  return d3.max(labels,label=>text(label).length)*fontSize*.56||60;
}

// Each column has its own unit (×, %, count) and its own min–max colour scale.
const PILON_METRICS=[
  {column:'Pilon Coverage',label:'Coverage',unit:'×',format:value=>`${d3.format(',.1f')(value)}×`,help:'Median read depth Pilon reported for the assemblies (× = reads per base).'},
  {column:'Pilon Confirmed %',label:'Confirmed bases',unit:'%',format:value=>`${d3.format('.2f')(value)}%`,help:'Median percentage of bases Pilon confirmed with the reads.'},
  {column:'Pilon Corrected snps',label:'SNPs fixed',unit:'n',format:value=>d3.format(',.1~f')(value),help:'Median number of substitutions Pilon corrected.'},
  {column:'Pilon Corrected insertions',label:'Insertions fixed',unit:'n',format:value=>d3.format(',.1~f')(value),help:'Median number of insertions Pilon corrected.'},
  {column:'Pilon Corrected deletions',label:'Deletions fixed',unit:'n',format:value=>d3.format(',.1~f')(value),help:'Median number of deletions Pilon corrected.'}
];

function renderPilonMetrics() {
  const rows=REPORT.summary.filter(matches);
  const groupCol=singleSelectedProject() ? 'Seed Input' : 'Project name';
  const groups=unique(rows,groupCol);
  if(!groups.length){
    return emptyChart('pilonMetricsHeatmap','No Pilon data.');
  }
  clearChart('pilonMetricsHeatmap');

  const container=document.getElementById('pilonMetricsHeatmap');
  const width=Math.max(520,container.clientWidth||900);
  const labels=groups.map(group=>groupCol==='Project name'?projectDisplayText(projectRecord(group)):text(group));
  const rowHeight=Math.max(18,Math.min(30,560/groups.length));
  const margin={top:36,right:0,bottom:30,left:Math.min(360,Math.max(110,svgLabelWidth(labels)+16))};
  const height=margin.top+groups.length*rowHeight+margin.bottom;
  const svg=d3.select('#pilonMetricsHeatmap').append('svg').attr('viewBox',`0 0 ${width} ${height}`).attr('width',width).attr('height',height);
  const x=d3.scaleBand().domain(PILON_METRICS.map(metric=>metric.column)).range([margin.left,width-margin.right]).padding(0);
  const y=d3.scaleBand().domain(groups.map(text)).range([margin.top,height-margin.bottom]).padding(0);
  const color=d3.scaleSequential(d3.interpolateGnBu).domain([0,1]);
  const cells=[];

  PILON_METRICS.forEach(metric=>{
    const med=groupMedian(rows,groupCol,metric.column);
    const values=[...med.values()].filter(value=>value!==null);
    const extent=d3.extent(values);
    metric.extent=extent;
    groups.forEach(group=>{
      const actual=med.get(text(group));
      if(actual===undefined||actual===null)return;
      const position=extent[0]===extent[1]?null:(actual-extent[0])/(extent[1]-extent[0]);
      cells.push({group,metric,actual,position});
    });
    // Column title with its unit and the range of the colour scale.
    const cx=x(metric.column)+x.bandwidth()/2;
    svg.append('text').attr('x',cx).attr('y',14).attr('text-anchor','middle').attr('font-size',11).attr('font-weight',700).attr('fill','#0f172a').attr('data-help',metric.help).text(`${metric.label} (${metric.unit})`);
    svg.append('text').attr('x',cx).attr('y',28).attr('text-anchor','middle').attr('font-size',9.5).attr('fill','#64748b')
      .text(values.length?(extent[0]===extent[1]?`all ${metric.format(extent[0])}`:`${metric.format(extent[0])} → ${metric.format(extent[1])}`):'no data');
  });

  svg.append('g').selectAll('rect').data(cells).join('rect')
    .attr('x',cell=>x(cell.metric.column)).attr('y',cell=>y(text(cell.group)))
    .attr('width',x.bandwidth()).attr('height',y.bandwidth()).attr('fill',cell=>cell.position===null?'#e2e8f0':color(cell.position))
    .on('mousemove',(event,cell)=>hover(event,`${groupCol==='Project name'?projectDisplayHtml(projectRecord(cell.group)):`<strong>${esc(cell.group)}</strong>`}<br>${esc(cell.metric.label)}: <b>${cell.metric.format(cell.actual)}</b> (median)<br>${cell.position===null?'Same value in every row (grey)':`Column range: ${cell.metric.format(cell.metric.extent[0])} to ${cell.metric.format(cell.metric.extent[1])}`}`))
    .on('mouseleave',unhover);
  // Thin separators between metric columns: each column is a separate scale.
  PILON_METRICS.slice(1).forEach(metric=>svg.append('line').attr('x1',x(metric.column)).attr('x2',x(metric.column)).attr('y1',margin.top).attr('y2',height-margin.bottom).attr('stroke','#ffffff').attr('stroke-width',2));

  if(pilonShowValues&&y.bandwidth()>=12){
    svg.append('g').selectAll('text').data(cells).join('text')
      .attr('x',cell=>x(cell.metric.column)+x.bandwidth()/2).attr('y',cell=>y(text(cell.group))+y.bandwidth()/2+3.5)
      .attr('text-anchor','middle').attr('font-size',Math.min(11,y.bandwidth()*.55)).attr('font-weight',650)
      .attr('fill',cell=>cell.position!==null&&cell.position>.55?'#ffffff':'#0f172a').attr('pointer-events','none')
      .text(cell=>cell.metric.format(cell.actual));
  }

  const yAxis=svg.append('g').attr('class','axis').attr('transform',`translate(${margin.left},0)`).call(d3.axisLeft(y).tickSize(0).tickPadding(6));
  yAxis.select('.domain').remove();
  yAxis.selectAll('text').attr('font-size',10.5);
  if(groupCol==='Project name')styleProjectAxisTicks(yAxis);

  // Horizontal legend: the colour is the position inside each column's own range, not a percentage.
  const legendWidth=180, legendX=margin.left, legendY=height-14;
  const gradient=svg.append('defs').append('linearGradient').attr('id','pilonMetricsGradient');
  d3.range(0,1.01,.1).forEach(value=>gradient.append('stop').attr('offset',`${Math.round(value*100)}%`).attr('stop-color',color(value)));
  svg.append('text').attr('x',legendX).attr('y',legendY+8).attr('font-size',9.5).attr('fill','#64748b').text('Column minimum');
  svg.append('rect').attr('x',legendX+92).attr('y',legendY).attr('width',legendWidth).attr('height',9).attr('rx',2).attr('fill','url(#pilonMetricsGradient)');
  svg.append('text').attr('x',legendX+100+legendWidth).attr('y',legendY+8).attr('font-size',9.5).attr('fill','#64748b').text('Column maximum · grey: same value in every row · each column uses its own unit and scale');
}

function renderGroupedBars(id, groups, series, yLabel, projectGroups=false, valueFormat=',.2~f', unit='') {
  if(!groups.length) return emptyChart(id,'No data.');
  clearChart(id);
  const {width}=chartSize(id);
  const labels=groups.map(group=>projectGroups?projectDisplayText(projectRecord(group)):text(group));
  const rotated=projectGroups||groups.length>7;
  const bottom=rotated?Math.min(320,svgLabelWidth(labels)+(projectGroups?24:10)):48;
  const height=Math.max(410,280+bottom);
  const margin={top:38,right:20,bottom,left:66};
  const svg=d3.select('#'+id).append('svg').attr('viewBox',`0 0 ${width} ${height}`);
  document.getElementById(id).style.minHeight='0';
  const x0=d3.scaleBand().domain(groups.map(text)).range([margin.left,width-margin.right]).padding(.18);
  const x1=d3.scaleBand().domain(series.map(s=>s.name)).range([0,x0.bandwidth()]).padding(.08);
  const max=d3.max(series,s=>d3.max(s.values,v=>v||0))||1;
  const y=d3.scaleLinear().domain([0,max]).nice().range([height-margin.bottom,margin.top]);
  drawLegend(svg,series.map(s=>s.name),width);
  series.forEach((s,si)=>{
    svg.append('g').selectAll('rect').data(groups.map((g,i)=>({group:g,value:s.values[i]}))).join('rect')
      .attr('x',d=>x0(text(d.group))+x1(s.name)).attr('y',d=>y(d.value||0)).attr('width',x1.bandwidth()).attr('height',d=>y(0)-y(d.value||0)).attr('fill',palette[si%palette.length])
      .on('mousemove',(event,d)=>hover(event,`${projectGroups?projectDisplayHtml(projectRecord(d.group)):`<strong>${esc(d.group)}</strong>`}<br>${esc(s.name)}: ${d3.format(valueFormat)(d.value||0)}${unit} (median)`)).on('mouseleave',unhover);
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
  renderGroupedBars('pilonBeforeAfterChart',groups,[{name:'Before Pilon',values:groups.map(g=>before.get(text(g))??0)},{name:'After Pilon',values:groups.map(g=>after.get(text(g))??0)}],'Genome length (bp)',!singleSelectedProject(),',.0f',' bp');
}

function renderPilonCorrections() {
  const rows=REPORT.summary.filter(matches), groupCol=singleSelectedProject()?'K-mer':'Project name', groups=unique(rows,groupCol);
  const cols=[['Pilon Corrected snps','SNPs'],['Pilon Corrected insertions','Insertions'],['Pilon Corrected deletions','Deletions']];
  const series=cols.map(([col,name])=>{const med=groupMedian(rows,groupCol,col);return {name,values:groups.map(g=>med.get(text(g))??0)}});
  renderGroupedBars('pilonCorrectionsChart',groups.map(g=>singleSelectedProject()?`K ${g}`:g),series,'Median corrections',!singleSelectedProject(),',.1~f');
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
  const coverageTrackHeight=genomes.some(genome=>coverageWindowsFor(genome))?46:0;
  const repeatLineHeight=12;
  // Each repeat gets its own summary line under the assembly name, so rows grow with the repeat count.
  const genomeRowHeight=genome=>{
    const count=(repeatsByAssembly.get(genome['Assembly key'])||[]).length;
    return Math.max(92+coverageTrackHeight,72+Math.max(0,count-1)*repeatLineHeight+(coverageTrackHeight?30:16));
  };
  const groupGap=22;
  const topMargin=14;
  const bottomMargin=24;
  const totalHeight=topMargin+groups.reduce((sum,group)=>sum+headerHeight+d3.sum(group.assemblies,genomeRowHeight)+groupGap,0)+bottomMargin;

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
    let rowCursor=rowsStart;

    groupAssemblies.forEach((genome,index)=>{
      const y0=rowCursor;
      const rowHeight=genomeRowHeight(genome);
      rowCursor+=rowHeight;
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

      svg.append('text')
        .attr('x',14)
        .attr('y',y0+56)
        .attr('font-size',9.5)
        .attr('font-weight',650)
        .attr('fill','#475569')
        .text(assemblyRepeats.length?`${assemblyRepeats.length} tandem repeat${assemblyRepeats.length===1?'':'s'} (TRF)`:'No tandem repeats');
      assemblyRepeats.forEach((repeat,repeatIndex)=>{
        const line=svg.append('text').attr('x',14).attr('y',y0+72+repeatIndex*repeatLineHeight).attr('font-size',8.6).attr('fill','#64748b');
        line.append('tspan').attr('font-weight',700).attr('fill',repeatColor(text(repeat['Repeat family label'])||text(repeat.Consensus)||'Repeat')).text(`Repeat ${repeatIndex+1}: `);
        line.append('tspan').text(`${text(repeat['Repeat length'])} bp = ${text(repeat['Copy Number'])} copies of ${text(repeat['Consensus Size'])} bp, consensus `);
        line.append('tspan').attr('font-family','ui-monospace, SFMono-Regular, Menlo, Consolas, monospace').attr('fill','#0f172a').text(truncateSequence(repeat.Consensus,18));
      });

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

      drawPilonChangeMarks(svg,genome,x,plusY,minusY);
      if(coverageTrackHeight){
        drawCoverageTrack(svg,genome,x,y0+84,coverageTrackHeight-8,genomeLength);
        const depthStats=coverageByRun.get(runCopyKey(genome));
        if(depthStats)svg.append('text').attr('x',14).attr('y',y0+72+Math.max(0,assemblyRepeats.length-1)*repeatLineHeight+15).attr('font-size',8.6).attr('fill','#0173B2')
          .text(`Depth: mean ${d3.format(',.1f')(num(depthStats['Mean depth'],0))}×, median ${d3.format(',')(num(depthStats['Median depth'],0))}×, weakest ${num(depthStats['Window size'],50)} bp window ${d3.format(',.0f')(num(depthStats['Lowest window mean depth'],0))}×${text(depthStats['Coordinate system']).startsWith('C')?'':' (pre-Pilon file)'}`);
      }

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
          .on('mousemove',event=>hover(event,`<b>${esc(family)}</b><br>${projectDisplayHtml(genome)}${locationText(genome)?`<br>Location: ${esc(locationText(genome))}`:''}<br>Seed ${esc(group.seed)} · K-mer ${esc(group.kmer)}<br>${esc(repeat.Start)}–${esc(repeat.End)} bp<br>Repeat length: ${esc(repeat['Repeat length'])}<br>Consensus size: ${esc(repeat['Consensus Size'])}<br>Copies: ${esc(repeat['Copy Number'])}<br>${esc(repeat['Gene context'])}<br><b>Consensus</b><br><span style="font-family:monospace;word-break:break-all">${esc(repeat.Consensus)}</span>`))
          .on('mouseleave',unhover);

        const consensusLabel=truncateSequence(repeat.Consensus,24);
        if(consensusLabel){
          const labelWidth=consensusLabel.length*5.3;
          const afterBlock=repeatStart+repeatWidth+5;
          const fitsAfter=afterBlock+labelWidth<width-plotRight;
          svg.append('text')
            .attr('x',fitsAfter?afterBlock:repeatStart-5)
            .attr('y',repeatY+3.5)
            .attr('text-anchor',fitsAfter?'start':'end')
            .attr('font-size',8.8)
            .attr('font-family','ui-monospace, SFMono-Regular, Menlo, Consolas, monospace')
            .attr('fill','#334155')
            .attr('pointer-events','none')
            .text(consensusLabel);
        }
      });
    });

    groupY=rowCursor+groupGap;
  });
}

function truncateSequence(value,maximum) {
  const sequence=text(value).trim();
  return sequence.length>maximum?`${sequence.slice(0,maximum-1)}…`:sequence;
}

const ORGANPIPE=REPORT.organpipe||{};
function runCopyKey(row) {
  return [text(row['Project name']).trim(),normalizedRunValue(row['Seed order']),normalizedRunValue(row['K-mer']),normalizedRunValue(row['Assembly copy'])].join('\0');
}
const coverageWindowsByRun=new Map((ORGANPIPE.coverage_windows||[]).filter(item=>text(item['Coordinate system']).startsWith('C')).map(item=>[runCopyKey(item),item]));
const pilonChangesByRun=d3Group(ORGANPIPE.pilon_changes||[],runCopyKey);
const coverageByRun=new Map((ORGANPIPE.coverage||[]).map(row=>[runCopyKey(row),row]));
const pilonBreaksByRun=d3Group(ORGANPIPE.pilon_breaks||[],runCopyKey);
function d3Group(rows,keyFn){const map=new Map();rows.forEach(row=>{const key=keyFn(row);if(!map.has(key))map.set(key,[]);map.get(key).push(row);});return map;}
function coverageWindowsFor(genome){return coverageWindowsByRun.get(runCopyKey(genome))||null;}
function organpipeRows(key){return (ORGANPIPE[key]||[]).filter(matches);}

function drawCoverageTrack(svg,genome,x,top,height,genomeLength) {
  const item=coverageWindowsFor(genome);
  const baselineY=top+height;
  // Rotated so it stays clear of the tick values of the depth axis.
  const labelX=x.range()[0]-38, labelY=top+height/2;
  svg.append('text').attr('x',labelX).attr('y',labelY).attr('transform',`rotate(-90,${labelX},${labelY})`).attr('text-anchor','middle').attr('font-size',8.5).attr('font-weight',700).attr('fill','#94a3b8').text('Depth');
  if(!item||!(item.Windows||[]).length){
    svg.append('text').attr('x',x.range()[0]).attr('y',top+height/2+3).attr('font-size',8.5).attr('fill','#94a3b8').text('No rotated depth file');
    return;
  }
  const size=num(item['Window size'],50);
  const windows=item.Windows;
  const maximum=d3.max(windows)||1;
  // Cap the scale at 2.5x the median window so a repeat spike does not flatten the profile.
  const cap=Math.min(maximum,Math.max(1,2.5*(d3.median(windows)||1)));
  const y=d3.scaleLinear().domain([0,cap]).range([baselineY,top]).clamp(true);
  const points=windows.map((value,index)=>({start:index*size+1,end:Math.min(genomeLength,(index+1)*size),value}));
  const area=d3.area().curve(d3.curveStepAfter).x(d=>x(d.start)).y0(baselineY).y1(d=>y(d.value));
  svg.append('path').datum(points.concat([{start:points[points.length-1].end,value:points[points.length-1].value}])).attr('d',area).attr('fill','#0173B2').attr('fill-opacity',.28).attr('stroke','#0173B2').attr('stroke-width',.6);
  const breaks=pilonBreaksByRun.get(runCopyKey(genome))||[];
  breaks.filter(row=>num(row['Rotated start'])!==null).forEach(row=>{
    svg.append('rect').attr('x',x(num(row['Rotated start']))).attr('y',top).attr('width',Math.max(2,x(num(row['Rotated end']))-x(num(row['Rotated start'])))).attr('height',height)
      .attr('fill','#D55E00').attr('fill-opacity',.22)
      .on('mousemove',event=>hover(event,`<b>Unresolved Pilon break</b><br>${esc(row['Rotated start'])}–${esc(row['Rotated end'])} bp (rotated)<br>${esc(row['Pilon message'])}`)).on('mouseleave',unhover);
  });
  svg.append('rect').attr('x',x.range()[0]).attr('y',top).attr('width',Math.max(1,x(genomeLength)-x.range()[0])).attr('height',height).attr('fill','transparent')
    .on('mousemove',event=>{
      const position=x.invert(d3.pointer(event)[0]);
      const point=points[Math.max(0,Math.min(points.length-1,Math.floor((position-1)/size)))];
      hover(event,`<b>Depth</b> ${d3.format(',.1f')(point.value)}×<br>${d3.format(',')(point.start)}–${d3.format(',')(point.end)} bp<br>Window ${size} bp, rotated coordinates`);
    }).on('mouseleave',unhover);
  const middle=d3.median(windows)||0;
  const axis=svg.append('g').attr('class','axis').attr('transform',`translate(${x.range()[0]-2},0)`).call(d3.axisLeft(y).tickValues([0,Math.round(middle),Math.round(cap)].filter((v,i,a)=>a.indexOf(v)===i)).tickFormat(value=>`${d3.format(',')(value)}×`).tickSize(3));
  axis.selectAll('text').attr('font-size',7.5);
  axis.select('.domain').attr('stroke','#cbd5e1');
  svg.append('line').attr('x1',x.range()[0]).attr('x2',x(genomeLength)).attr('y1',y(middle)).attr('y2',y(middle)).attr('stroke','#0f172a').attr('stroke-opacity',.35).attr('stroke-dasharray','3,3').attr('pointer-events','none');
  if(maximum>cap)svg.append('text').attr('x',x(genomeLength)-4).attr('y',top-2).attr('text-anchor','end').attr('font-size',8).attr('fill','#64748b').attr('pointer-events','none').text(`scale capped at ${d3.format(',')(Math.round(cap))}×, max ${d3.format(',')(Math.round(maximum))}×`);
  if(maximum>cap)points.filter(d=>d.value>cap).forEach(d=>svg.append('rect').attr('x',x(d.start)).attr('y',top-1).attr('width',Math.max(1,x(d.end)-x(d.start))).attr('height',2).attr('fill','#0f172a'));
}

function drawPilonChangeMarks(svg,genome,x,plusY,minusY) {
  const changes=(pilonChangesByRun.get(runCopyKey(genome))||[]).filter(row=>num(row['Rotated position'])!==null);
  changes.forEach(change=>{
    const cx=x(num(change['Rotated position']));
    svg.append('path').attr('d',`M${cx},${plusY-8} l-4,-7 h8 z`).attr('fill','#D55E00').attr('stroke','#ffffff').attr('stroke-width',.6)
      .on('mousemove',event=>hover(event,`<b>Pilon ${esc(text(change['Change type']).toLowerCase())}</b><br>Rotated position ${d3.format(',')(num(change['Rotated position']))}<br>Before Pilon ${esc(change['Position before Pilon'])}, after Pilon ${esc(change['Position after Pilon'])}<br>${esc(change.Reference)} → ${esc(change.Replacement)}`))
      .on('mouseleave',unhover);
  });
}

function renderReadQc() {
  const panel=document.getElementById('readQcPanel');
  const rows=(ORGANPIPE.read_qc||[]).filter(row=>state.projects.has(text(row['Project name'])));
  if(!rows.length){panel.innerHTML='';return;}
  const pct=value=>num(value)===null?'—':`${d3.format('.1f')(100*num(value))}%`;
  const count=value=>num(value)===null?'—':d3.format(',')(num(value));
  panel.innerHTML=`<div class="read-qc-grid">${rows.map(row=>`<div class="card read-qc-card"><div class="metric-label">Read QC (fastp)</div><div>${projectDisplayHtml(projectRecord(row['Project name']))}</div><dl>
    <dt>Reads before</dt><dd>${count(row['Reads before filtering'])}</dd>
    <dt>Reads after</dt><dd>${count(row['Reads after filtering'])}</dd>
    <dt>Q30 after</dt><dd>${pct(row['Q30 rate after'])}</dd>
    <dt>GC after</dt><dd>${pct(row['GC content after'])}</dd>
    <dt>Duplication</dt><dd>${pct(row['Duplication rate'])}</dd></dl></div>`).join('')}</div>`;
}

const completenessColors={'Present':'#029E73','Absent':'#D55E00','Duplicated':'#0173B2','Partial at origin':'#DE8F05'};
function assemblyRowLabel(row){return `${projectDisplayText(projectRecord(row['Project name']))} · ${text(row['Seed Input'])} · k${text(row['K-mer'])} · _${text(row['Assembly copy'])}`;}
function sortAssemblyRows(rows){return rows.slice().sort((a,b)=>text(a['Project name']).localeCompare(text(b['Project name']),undefined,{numeric:true})||text(a['Seed Input']).localeCompare(text(b['Seed Input']),undefined,{numeric:true})||num(a['K-mer'],0)-num(b['K-mer'],0)||num(a['Assembly copy'],0)-num(b['Assembly copy'],0));}

function renderCompletenessHeatmap() {
  const rows=sortAssemblyRows(organpipeRows('completeness'));
  const genes=ORGANPIPE.expected_markers||[];
  if(!rows.length||!genes.length)return emptyChart('completenessHeatmap','No MITOS2 results for these filters.');
  clearChart('completenessHeatmap');
  const container=document.getElementById('completenessHeatmap');
  const width=Math.max(640,container.clientWidth||1100);
  const rowHeight=16, top=104, orderWidth=78;
  // Projects get a titled gap; each Seed + K-mer combination inside a project gets a smaller gap.
  const projectGap=30, runGap=9;
  const labelWidth=Math.round(Math.min(300,Math.max(190,width*.2)));
  const cell=Math.max(12,(width-labelWidth-orderWidth-12)/genes.length);
  const gridRight=labelWidth+genes.length*cell;
  let cursor=top, previousProject=null, previousRun=null;
  const layout=rows.map(row=>{
    const project=text(row['Project name']), run=`${project}\0${text(row['Seed Input'])}\0${text(row['K-mer'])}`;
    let header=null;
    if(project!==previousProject){ if(previousProject!==null)cursor+=projectGap; else cursor+=projectGap-8; header=cursor-8; }
    else if(run!==previousRun)cursor+=runGap;
    previousProject=project; previousRun=run;
    const item={row,y:cursor,header,newRun:run};
    cursor+=rowHeight;
    return item;
  });
  const height=cursor+16;
  const svg=d3.select('#completenessHeatmap').append('svg').attr('width',width).attr('height',height).attr('viewBox',`0 0 ${width} ${height}`);
  genes.forEach((gene,index)=>{
    svg.append('text').attr('transform',`translate(${labelWidth+index*cell+cell/2+3},${top-6}) rotate(-60)`).attr('font-size',10).attr('fill','#334155').text(gene);
  });
  svg.append('text').attr('x',gridRight+10).attr('y',top-8).attr('font-size',10).attr('font-weight',700).attr('fill','#334155').text('Gene order');
  // Shade each Seed + K-mer block so the groups read as units.
  d3.groups(layout,item=>item.newRun).forEach(([,items],index)=>{
    const first=items[0].y, last=items[items.length-1].y+rowHeight;
    svg.append('rect').attr('x',4).attr('y',first-2).attr('width',width-8).attr('height',last-first+4).attr('rx',5).attr('fill',index%2?'#f8fafc':'#eef4f8');
  });
  layout.forEach(({row,y,header})=>{
    if(header!==null){
      const location=locationText(projectRecord(row['Project name']));
      const title=svg.append('text').attr('x',8).attr('y',header).attr('font-size',11.5).attr('fill','#0f172a');
      setSvgProjectLabel(title,projectRecord(row['Project name']),{suffix:location?`  ·  ${location}`:''});
      svg.append('line').attr('x1',8).attr('x2',width-8).attr('y1',header+5).attr('y2',header+5).attr('stroke','#94a3b8').attr('stroke-width',.8);
    }
    svg.append('text').attr('x',labelWidth-8).attr('y',y+rowHeight-4).attr('text-anchor','end').attr('font-size',10).attr('fill','#0f172a').text(`${text(row['Seed Input'])} · k${text(row['K-mer'])} · _${text(row['Assembly copy'])}`);
    genes.forEach((gene,c)=>{
      const status=text(row[gene])||'Absent';
      svg.append('rect').attr('x',labelWidth+c*cell+1).attr('y',y+1).attr('width',cell-2).attr('height',rowHeight-2).attr('rx',2).attr('fill',completenessColors[status]||'#cbd5e1')
        .on('mousemove',event=>hover(event,`<b>${esc(gene)}</b>: ${esc(status)}<br>${esc(assemblyRowLabel(row))}<br>${esc(row['Genes present'])} of ${genes.length} genes present`)).on('mouseleave',unhover);
    });
    const same=row['Gene order matches modal']===true;
    svg.append('text').attr('x',gridRight+10).attr('y',y+rowHeight-4).attr('font-size',10).attr('font-weight',650).attr('fill',same?'#029E73':'#D55E00').text(same?'Modal':'Differs')
      .on('mousemove',event=>hover(event,`<b>Gene order</b><br>${esc(row['Gene order'])}${same?'':`<br><br><b>Project modal order</b><br>${esc(row['Modal gene order'])}`}`)).on('mouseleave',unhover);
  });
  const legend=svg.append('g').attr('transform',`translate(${labelWidth},14)`);
  Object.entries(completenessColors).forEach(([label,color],index)=>{
    legend.append('rect').attr('x',index*140).attr('y',0).attr('width',12).attr('height',12).attr('rx',2).attr('fill',color);
    legend.append('text').attr('x',index*140+17).attr('y',10).attr('font-size',11).attr('fill','#334155').text(label);
  });
}

function qualitySettings() {
  const settings=ORGANPIPE.settings||{};
  const coverageRow=(ORGANPIPE.coverage||[])[0]||{};
  const recruitmentRow=(ORGANPIPE.recruitment||[])[0]||{};
  return {
    depth:num(settings.low_depth_threshold,num(coverageRow['Low-depth threshold'],10)),
    alertPercent:num(settings.low_coverage_alert_percent,5),
    window:num(settings.window_size,num(coverageRow['Window size'],50)),
    identity:num(settings.identity_threshold,num(recruitmentRow['Identity threshold'],98)),
    genes:(ORGANPIPE.expected_markers||[]).length||37
  };
}

function qualityColumns() {
  const q=qualitySettings();
  return [
    {group:'Sample',key:'project',label:'Project / species',help:'Project and species of the assembly. This column and the next stay visible while the table scrolls sideways.'},
    {group:'Assembly',key:'run',label:'Seed · K-mer · copy',help:'Seed used by NOVOPlasty, K-mer size and assembly copy (_1 is the main contig set, _2 the alternative copy NOVOPlasty writes when it finds two options).'},
    {group:'Assembly',key:'status',label:'Circular',help:'Whether NOVOPlasty closed the assembly into a circle.'},
    {group:'Annotation (MITOS2)',key:'genes',label:'Genes',help:`Number of the ${q.genes} expected mitochondrial genes (13 protein-coding, 2 rRNAs, 22 tRNAs) that MITOS2 annotated. Green: all present. Orange: some missing; the heatmap above shows which.`},
    {group:'Annotation (MITOS2)',key:'order',label:'Order',help:'Modal: same order and strand as the most common order among the complete assemblies of the project. Differs: at least one gene is out of place, often a sign of a misassembly or of a partial assembly.'},
    {group:'Annotation (MITOS2)',key:'integrity',label:'Integrity',help:'Errors and warnings of the annotation checks (internal stops, frame, start/stop codons, origin, length). Hover for the list; the Annotation integrity table below has every detail.'},
    {group:'Coverage (samtools depth)',key:'depth',label:'Mean (×)',help:`Mean number of reads covering each base. (A) means the rotated depth file was missing and the pre-Pilon file was used. Red when the mean is below ${q.depth}×.`},
    {group:'Coverage (samtools depth)',key:'cv',label:'CV',help:'Coefficient of variation of the depth (standard deviation / mean). Values near 0 mean even coverage; high values point to spikes (repeats, collapsed copies) or gaps.'},
    {group:'Coverage (samtools depth)',key:'low',label:`< ${q.depth}× (%)`,help:`Percentage of positions with fewer than ${q.depth} reads. Orange above ${q.alertPercent}%, which also raises the Low coverage alert.`},
    {group:'Coverage (samtools depth)',key:'window',label:`Weakest ${q.window} bp`,help:`Lowest mean depth among consecutive ${q.window} bp windows, and the position where that window starts. Pinpoints the least supported region.`},
    {group:'Read recruitment (BLAST)',key:'reads',label:'Reads',help:'Reads NOVOPlasty used to build the assembly that BLAST aligned back to it.'},
    {group:'Read recruitment (BLAST)',key:'mismatch',label:`< ${q.identity}% id. (%)`,help:`Share of aligned reads with identity below ${q.identity}%. Higher values can indicate sequencing errors, mixed haplotypes, heteroplasmy or nuclear copies (NUMTs). The bar is relative to the highest value in view.`},
    {group:'Read recruitment (BLAST)',key:'target',label:'Covered (%)',help:'Percentage of the assembly covered by at least one aligned read. Orange below 100%.'},
    {group:'Pilon',key:'changes',label:'Fixes',help:'Changes Pilon made to the assembly (insertions, deletions, substitutions), read from the .changes file. They are marked with triangles in the genome structure.'},
    {group:'Pilon',key:'breaks',label:'Breaks',help:'Regions Pilon tried to fix but could not (NoSolution in pilon.log). Orange when there is at least one.'},
    {group:'Junction',key:'junction',label:'Support',help:'Reads crossing the point where NOVOPlasty closed the circle: Supported, Weak or Unsupported, with spanning reads / flanking pairs. NA when the assembly is not circularized or the BAM is missing.'},
    {group:'Alerts',key:'alerts',label:'Alerts',help:'Automatic checks combining the columns above. Hover an alert to read the detail.'}
  ];
}

function renderQualityGuide() {
  const body=document.getElementById('qualityGuideBody');
  const groups=d3.groups(qualityColumns(),column=>column.group);
  body.innerHTML=groups.map(([group,columns])=>`<div class="quality-guide-group"><h4>${esc(group)}</h4><dl>${columns.map(column=>`<dt>${esc(column.label)}</dt><dd>${esc(column.help)}</dd>`).join('')}</dl></div>`).join('')
    +'<div class="quality-guide-group"><h4>Source of the reads</h4><dl><dd>Coverage, read recruitment and junction support use the reads NOVOPlasty assembled (<code>Assembled_reads</code>). They tend to agree with the assembly by construction: they flag problems, but do not prove an assembly is correct.</dd></dl></div>';
}

const junctionByAssembly=new Map((ORGANPIPE.junction||[]).map(row=>[text(row.Assembly),row]));
const integrityByAssembly=new Map((ORGANPIPE.integrity||[]).map(row=>[text(row.Assembly),row]));

// Integrity alerts (errors + warnings of all copies of a run) as a column of the Assembly data table.
(function addIntegrityColumn() {
  if(!(ORGANPIPE.integrity||[]).length)return;
  const sums=new Map();
  ORGANPIPE.integrity.forEach(row=>sums.set(rowKey(row),(sums.get(rowKey(row))||0)+num(row['Integrity alerts'],0)));
  REPORT.summary.forEach(row=>{ if(sums.has(rowKey(row)))row['Integrity alerts']=sums.get(rowKey(row)); });
  assemblyColumns.push('Integrity alerts');
})();

function renderQualityTable() {
  const q=qualitySettings();
  const columns=qualityColumns();
  const baseRows=sortAssemblyRows(organpipeRows('completeness').length?organpipeRows('completeness'):organpipeRows('coverage'));
  const byKey=key=>new Map((ORGANPIPE[key]||[]).map(row=>[text(row.Assembly),row]));
  const coverage=byKey('coverage'), recruitment=byKey('recruitment');
  const alerts=d3Group(ORGANPIPE.alerts||[],row=>text(row.Assembly));
  const changes=d3Group(ORGANPIPE.pilon_changes||[],row=>text(row.Assembly));
  const breaks=d3Group(ORGANPIPE.pilon_breaks||[],row=>text(row.Assembly));
  const onlyAlerts=document.getElementById('qualityOnlyAlerts').checked;
  const query=text(document.getElementById('qualitySearch').value).trim().toLowerCase();
  const rows=baseRows.filter(row=>{
    const name=text(row.Assembly);
    if(onlyAlerts&&!(alerts.get(name)||[]).length)return false;
    if(!query)return true;
    const haystack=[projectDisplayText(projectRecord(row['Project name'])),row['Project name'],row['Seed Input'],`k${text(row['K-mer'])}`,name,...(alerts.get(name)||[]).map(a=>a['Alert type'])].map(text).join(' ').toLowerCase();
    return haystack.includes(query);
  });

  const groups=d3.groups(columns,column=>column.group);
  document.getElementById('qualityTableHead').innerHTML=
    `<tr class="group-head">${groups.map(([group,items],index)=>`<th colspan="${items.length}">${esc(group)}</th>`).join('')}</tr>`
    +`<tr class="column-head">${columns.map((column,index)=>`<th data-help="${esc(column.help)}" class="${index<2?'q-sticky':''}">${esc(column.label)}</th>`).join('')}</tr>`;

  const withAlerts=baseRows.filter(row=>(alerts.get(text(row.Assembly))||[]).length).length;
  document.getElementById('qualityTableCount').textContent=`${rows.length} of ${baseRows.length} assembl${baseRows.length===1?'y':'ies'} shown · ${withAlerts} with alerts · hover a column title for its definition`;
  document.getElementById('qualitySubtitle').textContent=!ORGANPIPE.available
    ? 'No OrganPipe quality files were found for this run.'
    : baseRows.length
      ? `Values read from the OrganPipe folders of ${new Set(baseRows.map(r=>text(r['Project name']))).size} project(s).`
      : 'No MITOS2, depth or BLAST results for the assemblies in the current filters.';

  const fmt=(value,format)=>num(value)===null?'—':d3.format(format)(num(value));
  const maxMismatch=d3.max(rows,row=>num((recruitment.get(text(row.Assembly))||{})['Percent below threshold'],0))||0;
  const cell=(content,cls='',title='')=>`<td class="${cls}"${title?` data-tooltip="${esc(title)}"`:''}>${content}</td>`;
  const junctionClass={'Supported':'q-ok','Weak':'q-warn','Unsupported':'q-bad'};
  let previousProject=null;
  document.getElementById('qualityTableBody').innerHTML=rows.map(row=>{
    const name=text(row.Assembly), cov=coverage.get(name)||{}, rec=recruitment.get(name)||{};
    const assemblyAlerts=alerts.get(name)||[];
    let header='';
    if(text(row['Project name'])!==previousProject){
      previousProject=text(row['Project name']);
      const projectRows=rows.filter(item=>text(item['Project name'])===previousProject);
      const flagged=projectRows.filter(item=>(alerts.get(text(item.Assembly))||[]).length).length;
      const location=locationText(projectRecord(previousProject));
      header=`<tr class="q-project"><td colspan="${columns.length}"><span class="row-head">${projectDisplayHtml(projectRecord(previousProject))}${location?` · ${esc(location)}`:''} <span class="table-count">· ${projectRows.length} assembl${projectRows.length===1?'y':'ies'} · ${flagged} with alerts</span></span></td></tr>`;
    }
    const summaryRow=summaryByRunKey.get(rowKey(row));
    const circular=summaryRow?summaryRow.Circularized===true:null;
    const present=num(row['Genes present']);
    const order=row['Gene order matches modal'];
    const depth=num(cov['Mean depth']);
    const low=num(cov['Percent below threshold']);
    const mismatch=num(rec['Percent below threshold']);
    const target=num(rec['Target coverage %']);
    const breakCount=(breaks.get(name)||[]).length;
    const integrity=integrityByAssembly.get(name);
    const junction=junctionByAssembly.get(name);
    const support=junction?text(junction['Junction support']):'';
    const coordinate=cov['Coordinate system']&&!text(cov['Coordinate system']).startsWith('C')?' <span class="q-sub">(A) pre-Pilon</span>':'';
    const mismatchBar=mismatch===null||maxMismatch<=0?0:Math.min(100,100*mismatch/maxMismatch);
    const chip=a=>`<span class="alert-chip ${esc(a.Severity)}" data-tooltip="${esc(a.Detail)}">${esc(a['Alert type'])}</span>`;
    const rest=assemblyAlerts.slice(2);
    const chips=assemblyAlerts.slice(0,2).map(chip).join('')+(rest.length?`<span class="alert-chip more" data-tooltip-html="${esc(rest.map(a=>`<b>${esc(a['Alert type'])}</b>: ${esc(a.Detail)}`).join('<br>'))}">+${rest.length} more</span>`:'');
    const integrityText=integrity?`${num(integrity.Errors,0)} / ${num(integrity.Warnings,0)}`:'—';
    return header+'<tr>'+[
      cell(projectDisplayHtml(projectRecord(row['Project name'])),'q-project-cell'),
      cell(`<strong>${esc(row['Seed Input'])}</strong> · k${esc(row['K-mer'])} · _${esc(row['Assembly copy'])}`,'q-run'),
      cell(circular===null?'—':(circular?'Yes':'No'),circular===null?'':(circular?'q-ok':'q-warn')),
      cell(present===null?'—':`${present}/${q.genes}`,present===null?'':(present>=q.genes?'q-ok':(present<q.genes/2?'q-bad':'q-warn'))),
      cell(order===true?'Modal':(order===false?'Differs':'—'),order===true?'q-ok':(order===false?'q-warn':'')),
      cell(integrityText,integrity?(num(integrity.Errors,0)?'q-bad':(num(integrity.Warnings,0)?'q-warn':'q-ok')):'',integrity?`errors / warnings${integrity.Checks?`: ${integrity.Checks}`:''}`:''),
      cell(`${fmt(depth,',.1f')}${coordinate}`,'q-num'+(depth!==null&&depth<q.depth?' q-bad':'')),
      cell(fmt(cov['Coefficient of variation'],'.2f'),'q-num'),
      cell(fmt(low,'.2f'),'q-num'+(low===null?'':(low>q.alertPercent?' q-warn':(low===0?' q-ok':'')))),
      cell(num(cov['Lowest window mean depth'])===null?'—':`${fmt(cov['Lowest window mean depth'],',.0f')}× <span class="q-sub">at ${fmt(cov['Lowest window start'],',')}</span>`,'q-num'),
      cell(fmt(rec['Recruited reads'],','),'q-num'),
      mismatch===null?cell('—','q-num'):`<td class="data-bar-cell q-num" style="--bar-width:${mismatchBar.toFixed(1)}%;--bar-color:rgba(204,120,188,.35)"><div class="cell-bar"></div><span class="cell-value">${fmt(mismatch,'.2f')}</span></td>`,
      cell(target===null?'—':fmt(target,'.2~f'),'q-num'+(target===null?'':(target>=100?' q-ok':' q-warn'))),
      cell(String((changes.get(name)||[]).length),'q-num'),
      cell(String(breakCount),'q-num'+(breakCount?' q-warn':'')),
      cell(support&&support!=='NA'?`${esc(support)} <span class="q-sub">${fmt(junction['Spanning reads'],',')} reads / ${fmt(junction['Flanking pairs'],',')} pairs</span>`:'NA',junctionClass[support]||'',junction?text(junction.Note||junction['Junction mode']):''),
      cell(chips||'<span class="table-count">none</span>','q-alerts')
    ].join('')+'</tr>';
  }).join('') || `<tr><td colspan="${columns.length}" class="table-count" style="padding:18px">No assembly matches the table filters.</td></tr>`;
  pinColumns(document.getElementById('qualityTable'),2);
}

function renderIntegrityTable() {
  const showInfo=document.getElementById('integrityShowInfo').checked;
  const query=text(document.getElementById('integritySearch').value).trim().toLowerCase();
  const all=organpipeRows('integrity_issues');
  const rows=sortAssemblyRows(all.filter(row=>showInfo||text(row.Severity)!=='info').filter(row=>!query||[row['Project name'],row['Seed Input'],`k${text(row['K-mer'])}`,row.Assembly,row.Marker,row.Check,row.Detail].map(text).join(' ').toLowerCase().includes(query)));
  const severityClass={error:'q-bad',warning:'q-warn',info:''};
  const columns=['Project / species','Location','Seed · K-mer · copy','Gene','Check','Severity','Detail','Position'];
  document.getElementById('integrityHead').innerHTML=`<tr>${columns.map(c=>`<th>${esc(c)}</th>`).join('')}</tr>`;
  const counts=d3.rollup(all,v=>v.length,row=>text(row.Severity));
  const code=(ORGANPIPE.settings_phase2||{});
  document.getElementById('integrityCount').textContent=`${rows.length} shown · ${counts.get('error')||0} errors, ${counts.get('warning')||0} warnings, ${counts.get('info')||0} informative · genetic code ${text(code.genetic_code||'—')} (${text(code.genetic_code_source||'')})`;
  const shown=rows.slice(0,1500);
  document.getElementById('integrityBody').innerHTML=shown.map(row=>`<tr><td style="text-align:left">${projectDisplayHtml(projectRecord(row['Project name']))}</td><td style="text-align:left">${esc(locationText(projectRecord(row['Project name'])))}</td><td>${esc(row['Seed Input'])} · k${esc(row['K-mer'])} · _${esc(row['Assembly copy'])}</td><td><strong>${esc(row.Marker)}</strong></td><td>${esc(row.Check)}</td><td class="${severityClass[text(row.Severity)]||''}">${esc(row.Severity)}</td><td style="text-align:left;white-space:normal;min-width:260px">${esc(row.Detail)}</td><td>${esc(row.Start)}–${esc(row.End)} (${esc(row.Strand)})</td></tr>`).join('')
    +(rows.length>shown.length?`<tr><td colspan="8" class="table-count">${rows.length-shown.length} more rows in annotation_integrity/annotation_integrity_issues.tsv</td></tr>`:'')
    || '<tr><td colspan="8" class="table-count" style="padding:16px">No integrity issue for the current filters.</td></tr>';
  pinColumns(document.getElementById('integrityTable'),2);
}

function renderConcordance() {
  const grid=document.getElementById('concordanceGrid');
  grid.innerHTML='';
  const members=organpipeRows('concordance');
  const subtitle=document.getElementById('concordanceSubtitle');
  if(!members.length){subtitle.textContent='No concordance results for the current filters (the analysis needs at least two rotated genomes per project).';return;}
  const visible=new Set(members.map(row=>text(row.Assembly)));
  const pairs=(ORGANPIPE.concordance_pairs||[]).filter(pair=>visible.has(text(pair['Assembly A']))&&visible.has(text(pair['Assembly B'])));
  const pairMap=new Map(pairs.map(pair=>[`${pair['Assembly A']}\0${pair['Assembly B']}`,pair]));
  const getPair=(a,b)=>pairMap.get(`${a}\0${b}`)||pairMap.get(`${b}\0${a}`);
  const outside=members.filter(row=>row['In majority group']===false).length;
  subtitle.textContent=`${members.length} assemblies in ${new Set(members.map(row=>text(row['Project name']))).size} project(s); ${outside} outside the majority group of their sample (red labels). Darker cells mean higher identity; hatched cells compare less than the minimum coverage, usually a partial genome.`;
  const identities=pairs.map(pair=>num(pair['Identity %'])).filter(value=>value!==null);
  const minimum=Math.min(99,d3.min(identities)||99);
  const color=d3.scaleSequential(d3.interpolateBlues).domain([minimum,100]);
  d3.groups(members,row=>text(row['Project name'])).forEach(([project,rows])=>{
    rows=rows.slice().sort((a,b)=>num(a.Group,0)-num(b.Group,0)||text(a['Seed Input']).localeCompare(text(b['Seed Input']),undefined,{numeric:true})||num(a['K-mer'],0)-num(b['K-mer'],0)||num(a['Assembly copy'],0)-num(b['Assembly copy'],0));
    const card=document.createElement('div'); card.className='card concordance-card'; grid.appendChild(card);
    const groupsCount=new Set(rows.map(row=>row.Group)).size;
    card.innerHTML=`<div class="chart-title" style="font-size:13.5px">${projectDisplayHtml(projectRecord(project))}</div><div class="chart-subtitle">${rows.length} assemblies · ${groupsCount} group${groupsCount===1?'':'s'} · majority group ${esc(rows[0]['Majority group'])} with ${rows.filter(row=>row['In majority group']===true).length} assemblies</div>`;
    const holder=document.createElement('div'); card.appendChild(holder);
    // The matrix fills the card: columns share the width, rows keep a readable height.
    const width=Math.max(480,holder.clientWidth||card.clientWidth-28||900);
    const labelWidth=190, right=96;
    const cellWidth=(width-labelWidth-right)/rows.length;
    const cell=Math.max(10,Math.min(24,cellWidth));
    const shortLabel=row=>`${text(row['Seed Input'])} k${text(row['K-mer'])} _${text(row['Assembly copy'])}`;
    const showColumnLabels=cellWidth>=9;
    const top=showColumnLabels?Math.min(110,16+d3.max(rows,row=>shortLabel(row).length)*4.2):12;
    const height=top+rows.length*cell+12;
    const svg=d3.select(holder).append('svg').attr('width',width).attr('height',height).attr('viewBox',`0 0 ${width} ${height}`);
    const defs=svg.append('defs');
    defs.append('pattern').attr('id',`hatch-${project}`).attr('patternUnits','userSpaceOnUse').attr('width',4).attr('height',4).append('path').attr('d','M0,4 l4,-4').attr('stroke','#94a3b8').attr('stroke-width',1);
    rows.forEach((row,i)=>{
      const label=`${text(row['Seed Input'])} · k${text(row['K-mer'])} · _${text(row['Assembly copy'])}`;
      const inMajority=row['In majority group']===true;
      svg.append('text').attr('x',labelWidth-6).attr('y',top+i*cell+cell/2+3.5).attr('text-anchor','end').attr('font-size',Math.min(10.5,cell*.8)).attr('font-weight',inMajority?400:750).attr('fill',inMajority?'#334155':'#D55E00').text(`${label}${inMajority?'':` (group ${row.Group})`}`)
        .on('mousemove',event=>hover(event,`<b>${esc(label)}</b><br>Group ${esc(row.Group)} (${esc(row['Group size'])} assemblies)${inMajority?' · majority':''}<br>Genome ${d3.format(',')(num(row['Genome length'],0))} bp${row['Reverse-complemented']===true?' · reverse-complemented for the alignment':''}<br>Mean identity to the majority group: ${row['Mean identity to majority %']===null?'—':`${d3.format('.4f')(num(row['Mean identity to majority %']))}%`}`)).on('mouseleave',unhover);
      rows.forEach((other,j)=>{
        const x=labelWidth+j*cellWidth, y=top+i*cell;
        if(i===j){svg.append('rect').attr('x',x).attr('y',y).attr('width',cellWidth-1).attr('height',cell-1).attr('fill','#0f172a');return;}
        const pair=getPair(text(row.Assembly),text(other.Assembly));
        if(!pair)return;
        const identity=num(pair['Identity %']);
        const lowCoverage=num(pair['Coverage %'],100)<num((ORGANPIPE.settings_phase2||{}).group_min_coverage,95);
        svg.append('rect').attr('x',x).attr('y',y).attr('width',cellWidth-1).attr('height',cell-1).attr('fill',identity===null?'#e2e8f0':color(Math.max(minimum,identity)))
          .on('mousemove',event=>hover(event,`<b>${esc(label)}</b><br>vs ${esc(text(other['Seed Input']))} · k${esc(other['K-mer'])} · _${esc(other['Assembly copy'])}<br>Identity ${identity===null?'—':d3.format('.4f')(identity)+'%'} over ${d3.format(',')(num(pair['Compared columns'],0))} columns<br>Coverage ${d3.format('.2f')(num(pair['Coverage %'],0))}% · ${esc(pair.Indels)} indel events`)).on('mouseleave',unhover);
        if(lowCoverage)svg.append('rect').attr('x',x).attr('y',y).attr('width',cellWidth-1).attr('height',cell-1).attr('fill',`url(#hatch-${project})`).attr('pointer-events','none');
      });
    });
    if(showColumnLabels)rows.forEach((row,j)=>{
      const cx=labelWidth+j*cellWidth+cellWidth/2;
      const inMajority=row['In majority group']===true;
      svg.append('text').attr('x',cx).attr('y',top-5).attr('transform',`rotate(-50,${cx},${top-5})`).attr('font-size',Math.min(10,Math.max(8,cellWidth*.7))).attr('fill',inMajority?'#475569':'#D55E00').attr('font-weight',inMajority?400:700).text(shortLabel(row));
    });
    const legendX=labelWidth+rows.length*cellWidth+18;
    const legend=svg.append('g').attr('transform',`translate(${legendX},${top})`);
    const legendHeight=Math.min(140,Math.max(60,rows.length*cell));
    const gradientId=`concordanceGradient-${project}`;
    const gradient=defs.append('linearGradient').attr('id',gradientId).attr('x1','0%').attr('x2','0%').attr('y1','100%').attr('y2','0%');
    d3.range(0,101,10).forEach(value=>gradient.append('stop').attr('offset',`${value}%`).attr('stop-color',color(minimum+(100-minimum)*value/100)));
    legend.append('rect').attr('width',12).attr('height',legendHeight).attr('fill',`url(#${gradientId})`).attr('stroke','#cbd5e1');
    legend.append('g').attr('class','axis').attr('transform','translate(12,0)').call(d3.axisRight(d3.scaleLinear().domain([minimum,100]).range([legendHeight,0])).ticks(4).tickFormat(value=>`${d3.format('.2~f')(value)}%`));
  });
}

let rscuSelection=null;
function renderComposition() {
  const rows=sortAssemblyRows(organpipeRows('composition'));
  const subtitle=document.getElementById('compositionSubtitle');
  const code=ORGANPIPE.settings_phase2||{};
  subtitle.textContent=rows.length?`Genetic code ${text(code.genetic_code||2)} (${text(code.genetic_code_source||'default')}). Skews: AT = (A − T)/(A + T), GC = (G − C)/(G + C). Protein-coding genes are read 5'→3' on their own coding strand.`:'No composition results for the current filters.';
  const columns=[['Seed · K-mer · copy',row=>`<strong>${esc(row['Seed Input'])}</strong> · k${esc(row['K-mer'])} · _${esc(row['Assembly copy'])}`],['Length (bp)',row=>d3.format(',')(num(row['Genome length'],0))],
    ['GC %',row=>fmtNum(row['GC %'],'.2f')],['AT skew',row=>fmtNum(row['AT skew'],'.3f')],['GC skew',row=>fmtNum(row['GC skew'],'.3f')],
    ['PCG + GC %',row=>fmtNum(row['PCG + GC %'],'.2f')],['PCG + AT skew',row=>fmtNum(row['PCG + AT skew'],'.3f')],['PCG + GC skew',row=>fmtNum(row['PCG + GC skew'],'.3f')],
    ['PCG − GC %',row=>fmtNum(row['PCG - GC %'],'.2f')],['PCG − AT skew',row=>fmtNum(row['PCG - AT skew'],'.3f')],['PCG − GC skew',row=>fmtNum(row['PCG - GC skew'],'.3f')],
    ['Codons',row=>d3.format(',')(num(row['Codons counted'],0))]];
  document.getElementById('compositionHead').innerHTML=`<tr>${columns.map(([label])=>`<th>${esc(label)}</th>`).join('')}</tr>`;
  // The RefSeq genomes compared with each sample follow its assemblies, in grey.
  const accessions=referenceAccessionsByProject();
  const referenceRows=project=>(accessions.get(project)||[]).map(accession=>referenceCompositionByAccession.get(accession)).filter(Boolean);
  const referenceCount=new Set([...new Set(rows.map(row=>text(row['Project name'])))].flatMap(project=>referenceRows(project).map(ref=>text(ref.Accession)))).size;
  document.getElementById('compositionCount').textContent=`${rows.length} assembl${rows.length===1?'y':'ies'}${referenceCount?` · ${referenceCount} RefSeq genome${referenceCount===1?'':'s'} in grey under each sample`:''}`;
  const referenceLabel=ref=>`<span class="ref-badge">RefSeq</span><a href="https://www.ncbi.nlm.nih.gov/nuccore/${encodeURIComponent(text(ref.Accession))}" target="_blank" rel="noopener">${esc(ref.Accession)}</a> · <em>${esc(ref.Organism)}</em>`;
  const groups=d3.groups(rows,row=>text(row['Project name']));
  document.getElementById('compositionBody').innerHTML=groups.map(([project,items])=>{
    const location=locationText(projectRecord(project));
    const header=`<tr class="q-project"><td colspan="${columns.length}" style="text-align:left;background:#e8f3f9"><span class="row-head">${projectDisplayHtml(projectRecord(project))}${location?` · ${esc(location)}`:''}</span></td></tr>`;
    const assemblyRows=items.map(row=>`<tr>${columns.map(([,render])=>`<td>${render(row)}</td>`).join('')}</tr>`).join('');
    const refs=referenceRows(project).map(ref=>`<tr class="ref-row">${columns.map(([label,render],index)=>`<td>${index===0?referenceLabel(ref):render(ref)}</td>`).join('')}</tr>`).join('');
    return header+assemblyRows+refs;
  }).join('');
  pinColumns(document.getElementById('compositionTable'),1);
  renderCompositionStrip();

  renderRscu();
}

const AMINO_ACID_NAMES={A:'Ala',R:'Arg',N:'Asn',D:'Asp',C:'Cys',Q:'Gln',E:'Glu',G:'Gly',H:'His',I:'Ile',L:'Leu',K:'Lys',M:'Met',F:'Phe',P:'Pro',S:'Ser',T:'Thr',W:'Trp',Y:'Tyr',V:'Val','*':'Stop'};
const RSCU_SEGMENT_COLORS=['#0173B2','#DE8F05','#029E73','#CC78BC'];
let rscuView='stacked';

// Codon families: the codons of one amino acid sharing the first two bases (a codon box).
function rscuFamilies(rscu) {
  const families=d3.groups(rscu.codons.map((codon,index)=>({codon,index,aa:rscu.amino_acids[index]})),item=>`${item.aa}\0${item.codon.slice(0,2)}`)
    .map(([key,items])=>{
      const aa=items[0].aa, thirds=new Set(items.map(item=>item.codon[2]));
      const third=thirds.size===4?'N':(thirds.size===2&&thirds.has('T')&&thirds.has('C')?'Y':(thirds.size===2&&thirds.has('A')&&thirds.has('G')?'R':[...thirds].join('/')));
      items.sort((a,b)=>'TCAG'.indexOf(a.codon[2])-'TCAG'.indexOf(b.codon[2]));
      return {key,aa,name:AMINO_ACID_NAMES[aa]||aa,box:`${items[0].codon.slice(0,2)}${third}`,items};
    });
  const boxes=d3.rollup(families,v=>v.length,family=>family.aa);
  families.forEach(family=>{ family.label=boxes.get(family.aa)>1?`${family.name} ${family.box}`:family.name; });
  return families.sort((a,b)=>a.name.localeCompare(b.name)||a.box.localeCompare(b.box));
}

function rscuAssemblyLabel(row) {
  if(row.isReference)return `RefSeq ${text(row.Accession)} · ${shortSpeciesName(row.Organism)}`;
  return `${projectDisplayText(projectRecord(row['Project name']))} · ${text(row['Seed Input'])} · k${text(row['K-mer'])} · _${text(row['Assembly copy'])}`;
}

function renderRscu() {
  const rscu=ORGANPIPE.rscu||{codons:[],assemblies:[]};
  const select=document.getElementById('rscuSelect');
  const legend=document.getElementById('rscuLegend');
  const available=sortAssemblyRows((rscu.assemblies||[]).filter(matches));
  document.getElementById('rscuView').value=rscuView;
  const stacked=rscuView==='stacked';
  select.style.display=stacked?'':'none';
  document.getElementById('rscuSelectLabel').style.display=stacked?'':'none';
  if(!available.length){select.innerHTML='';legend.innerHTML='';emptyChart('rscuChart','No codon usage for the current filters.');return;}
  const recommended=new Set(organpipeRows('scores').filter(row=>row.Recommended===true).map(row=>text(row.Assembly)));
  const references=referenceRscuItems();
  const choices=[...available,...references];
  if(!rscuSelection||!choices.some(row=>text(row.Assembly)===rscuSelection))rscuSelection=text((available.find(row=>recommended.has(text(row.Assembly)))||available[0]).Assembly);
  const option=row=>`<option value="${esc(row.Assembly)}" ${text(row.Assembly)===rscuSelection?'selected':''}>${esc(rscuAssemblyLabel(row))}${recommended.has(text(row.Assembly))?' (recommended)':''}</option>`;
  select.innerHTML=references.length
    ? `<optgroup label="Assemblies">${available.map(option).join('')}</optgroup><optgroup label="RefSeq genomes">${references.map(option).join('')}</optgroup>`
    : available.map(option).join('');
  const families=rscuFamilies(rscu);
  clearChart('rscuChart');
  if(stacked)renderRscuStacked(rscu,families,choices.find(row=>text(row.Assembly)===rscuSelection));
  else renderRscuHeatmap(rscu,families,[...available,...references],recommended);
}

function renderRscuStacked(rscu,families,item) {
  const legend=document.getElementById('rscuLegend');
  legend.innerHTML='<span>Each bar stacks the RSCU of the synonymous codons of one codon box; the boxes beneath list those codons in the same color and order, from the bottom of the bar up, with n = number of times the codon was counted.</span><span>Dashed line: height of a box with no codon preference (every codon at RSCU 1).</span>';
  const container=document.getElementById('rscuChart');
  const margin={top:14,right:12,left:48};
  const width=Math.max(760,container.clientWidth||1100,margin.left+margin.right+families.length*50);
  const maxCodons=d3.max(families,family=>family.items.length)||4;
  const aaHeight=28, codonHeight=26, codonGap=2, gapBelowPlot=8;
  margin.bottom=gapBelowPlot+aaHeight+4+maxCodons*(codonHeight+codonGap)+26;
  const plotHeight=270;
  const height=margin.top+plotHeight+margin.bottom;
  const values=item.RSCU.map(value=>num(value,0));
  const counts=item.Counts.map(value=>num(value,0));
  const totals=families.map(family=>d3.sum(family.items,codon=>values[codon.index]));
  const svg=d3.select('#rscuChart').append('svg').attr('width',width).attr('height',height).attr('viewBox',`0 0 ${width} ${height}`);
  const x=d3.scaleBand().domain(families.map(family=>family.key)).range([margin.left,width-margin.right]).paddingInner(.14).paddingOuter(.06);
  const y=d3.scaleLinear().domain([0,Math.max(4,d3.max(totals)||0)]).nice().range([margin.top+plotHeight,margin.top]);
  svg.append('g').attr('class','grid-line').attr('transform',`translate(${margin.left},0)`).call(d3.axisLeft(y).ticks(6).tickSize(-(width-margin.left-margin.right)).tickFormat(''));
  svg.append('g').attr('class','axis').attr('transform',`translate(${margin.left},0)`).call(d3.axisLeft(y).ticks(6));
  svg.append('text').attr('transform','rotate(-90)').attr('x',-(margin.top+plotHeight/2)).attr('y',13).attr('text-anchor','middle').attr('font-size',10.5).attr('fill','#64748b').text('RSCU (stacked within each codon box)');
  // Text on the segment colors: white on blue and green, dark on orange and pink.
  const textColor=['#ffffff','#1f2937','#ffffff','#1f2937'];
  const tip=(codon,family)=>`<b>${esc(codon.codon)}</b> · ${esc(family.label)}<br>RSCU ${d3.format('.3f')(values[codon.index])} · n = ${d3.format(',')(counts[codon.index])} codons<br>${values[codon.index]>1.05?'Used more than its synonyms':(values[codon.index]<.95?'Used less than its synonyms':'No preference')}`;
  const highlight=(index,on)=>svg.selectAll(`.rscu-codon-${index}`).attr('stroke',on?'#0f172a':'#fff').attr('stroke-width',on?1.6:.6);
  families.forEach(family=>{
    const bx=x(family.key), bw=x.bandwidth();
    let base=0;
    family.items.forEach((codon,position)=>{
      const value=values[codon.index];
      svg.append('rect').attr('class',`rscu-codon-${codon.index}`).attr('x',bx).attr('y',y(base+value)).attr('width',bw).attr('height',Math.max(0,y(base)-y(base+value))).attr('fill',RSCU_SEGMENT_COLORS[position%4]).attr('stroke','#fff').attr('stroke-width',.6)
        .on('mouseenter',()=>highlight(codon.index,true)).on('mousemove',event=>hover(event,tip(codon,family))).on('mouseleave',()=>{highlight(codon.index,false);unhover();});
      base+=value;
    });
    // Without preference every codon has RSCU 1, so the stack of a box equals its number of codons.
    const expected=family.items.length;
    svg.append('line').attr('x1',bx-2).attr('x2',bx+bw+2).attr('y1',y(expected)).attr('y2',y(expected)).attr('stroke','#0f172a').attr('stroke-dasharray','3,2').attr('stroke-opacity',.55).attr('pointer-events','none');
    const aaTop=margin.top+plotHeight+gapBelowPlot;
    svg.append('rect').attr('x',bx).attr('y',aaTop).attr('width',bw).attr('height',aaHeight).attr('rx',3).attr('fill','#e2e8f0');
    svg.append('text').attr('x',bx+bw/2).attr('y',aaTop+12).attr('text-anchor','middle').attr('font-size',10.5).attr('font-weight',750).attr('fill','#0f172a').text(family.name);
    svg.append('text').attr('x',bx+bw/2).attr('y',aaTop+23).attr('text-anchor','middle').attr('font-size',8.5).attr('fill','#475569').attr('font-family','ui-monospace, monospace').text(family.box);
    family.items.forEach((codon,position)=>{
      const top=aaTop+aaHeight+4+position*(codonHeight+codonGap);
      svg.append('rect').attr('class',`rscu-codon-${codon.index}`).attr('x',bx).attr('y',top).attr('width',bw).attr('height',codonHeight).attr('rx',3).attr('fill',RSCU_SEGMENT_COLORS[position%4]).attr('stroke','#fff').attr('stroke-width',.6)
        .on('mouseenter',()=>highlight(codon.index,true)).on('mousemove',event=>hover(event,tip(codon,family))).on('mouseleave',()=>{highlight(codon.index,false);unhover();});
      svg.append('text').attr('x',bx+bw/2).attr('y',top+11).attr('text-anchor','middle').attr('font-size',9.5).attr('font-weight',750).attr('font-family','ui-monospace, monospace').attr('fill',textColor[position%4]).attr('pointer-events','none').text(codon.codon);
      svg.append('text').attr('x',bx+bw/2).attr('y',top+21.5).attr('text-anchor','middle').attr('font-size',8).attr('fill',textColor[position%4]).attr('pointer-events','none').text(`n=${counts[codon.index]}`);
    });
  });
  svg.append('text').attr('x',margin.left).attr('y',height-8).attr('font-size',10).attr('fill','#64748b').text(`${rscuAssemblyLabel(item)} · ${d3.format(',')(d3.sum(counts))} codons counted`);
}

function renderRscuHeatmap(rscu,families,assemblies,recommended) {
  const legend=document.getElementById('rscuLegend');
  const maximum=Math.max(2,d3.max(assemblies,row=>d3.max(row.RSCU,value=>num(value,0)))||2);
  const color=d3.scaleDiverging(t=>d3.interpolateRdBu(1-t)).domain([0,1,maximum]);
  legend.innerHTML=`<span><i style="background:${color(0)}"></i>0, codon not used</span><span><i style="background:${color(1)};border:1px solid #cbd5e1"></i>1, no preference</span><span><i style="background:${color(maximum)}"></i>${d3.format('.1f')(maximum)}, strongly preferred</span><span>Rows marked ★ are the recommended assemblies; RefSeq genomes are the italic rows at the bottom. An assembly whose row stands out from the others of its project and from the references deserves a look.</span>`;
  const container=document.getElementById('rscuChart');
  const width=Math.max(900,container.clientWidth||1100);
  const columns=families.flatMap(family=>family.items.map(codon=>({...codon,family})));
  const labelWidth=Math.min(380,Math.max(220,svgLabelWidth(assemblies.map(rscuAssemblyLabel),10)+28));
  const cellWidth=Math.max(11,(width-labelWidth-12)/columns.length);
  const rowHeight=14, top=78;
  let cursor=top, previous=null;
  const layout=assemblies.map(row=>{ const group=row.isReference?'\u0000refseq':text(row['Project name']); if(previous!==null&&group!==previous)cursor+=row.isReference?16:8; previous=group; const item={row,y:cursor}; cursor+=rowHeight; return item; });
  const height=cursor+12;
  const svgWidth=labelWidth+columns.length*cellWidth+12;
  const svg=d3.select('#rscuChart').append('svg').attr('width',svgWidth).attr('height',height).attr('viewBox',`0 0 ${svgWidth} ${height}`);
  let offset=0;
  families.forEach((family,index)=>{
    const x0=labelWidth+offset*cellWidth, w=family.items.length*cellWidth;
    svg.append('rect').attr('x',x0).attr('y',4).attr('width',w-2).attr('height',14).attr('rx',3).attr('fill',index%2?'#e2e8f0':'#cbd5e1');
    svg.append('text').attr('x',x0+w/2-1).attr('y',14.5).attr('text-anchor','middle').attr('font-size',w>34?9.5:8).attr('font-weight',700).attr('fill','#0f172a').text(w>40?family.label:family.name)
      .attr('data-help',`${family.label}: ${family.items.map(item=>item.codon).join(', ')}`);
    family.items.forEach((codon,j)=>{
      const cx=x0+(j+.5)*cellWidth;
      svg.append('text').attr('x',cx).attr('y',top-4).attr('transform',`rotate(-90,${cx},${top-4})`).attr('font-size',8.5).attr('font-family','ui-monospace, monospace').attr('fill','#475569').text(codon.codon);
    });
    offset+=family.items.length;
  });
  layout.forEach(({row,y})=>{
    const isPick=recommended.has(text(row.Assembly));
    const label=svg.append('text').attr('x',labelWidth-8).attr('y',y+rowHeight-3.5).attr('text-anchor','end').attr('font-size',9.5).attr('fill',row.isReference?'#475569':'#0f172a').attr('font-weight',isPick?700:400);
    if(row.isReference)label.attr('font-style','italic').text(rscuAssemblyLabel(row));
    else setSvgProjectLabel(label,projectRecord(row['Project name']),{suffix:` · ${text(row['Seed Input'])} · k${text(row['K-mer'])} · _${text(row['Assembly copy'])}${isPick?' ★':''}`});
    columns.forEach((codon,c)=>{
      const value=num(row.RSCU[codon.index],0);
      svg.append('rect').attr('x',labelWidth+c*cellWidth).attr('y',y).attr('width',cellWidth-.6).attr('height',rowHeight-.6).attr('fill',color(value))
        .on('mousemove',event=>hover(event,`<b>${esc(codon.codon)}</b> · ${esc(codon.family.label)}<br>${esc(rscuAssemblyLabel(row))}<br>RSCU ${d3.format('.3f')(value)} · ${d3.format(',')(num(row.Counts[codon.index],0))} codons`)).on('mouseleave',unhover);
    });
  });
}

function fmtNum(value,format) { return num(value)===null?'—':d3.format(format)(num(value)); }

const SCORE_COMPONENTS=[
  ['Annotation completeness (0-1)','Completeness','completeness'],['Integrity alerts (0-1)','Integrity','integrity'],['Junction support (0-1)','Junction','junction'],
  ['Coverage uniformity (0-1)','Coverage','coverage'],['Pilon confirmed bases (0-1)','Pilon','pilon'],['Majority concordance group (0-1)','Concordance','concordance'],['Closeness to modal length (0-1)','Length','length']
];

// What each score component measures, shown on the recommendation cards and in the ranking headers.
function scoreComponentHelp(key) {
  const settings=ORGANPIPE.settings_phase2||{};
  const q=qualitySettings();
  const tolerance=num(settings.score_length_tolerance_percent,5);
  return {
    completeness:`Genes MITOS2 annotated out of the ${q.genes} expected.`,
    integrity:'1 / (1 + annotation errors and warnings): 1 means no alert.',
    junction:'Reads across the point where the circle was closed: supported 1, weak 0.5, unsupported 0.',
    coverage:`Even read depth: (1 − CV) × (1 − share of bases below ${q.depth}×).`,
    pilon:'Share of bases Pilon confirmed without changing them.',
    concordance:'1 when the assembly is in the largest group of matching assemblies of the sample, otherwise 0.',
    length:`1 at the most common genome length of the project, falling to 0 at ${tolerance}% away from it.`
  }[key]||'';
}

function scoreBreakdownHtml(row) {
  const naValue=(ORGANPIPE.settings_phase2||{}).score_na_value;
  const naText=naValue===null||naValue===undefined?'NA, not counted':`NA, counted as ${naValue}`;
  return `<b>Score ${fmtNum(row.Score,'.1f')}</b> (weighted mean × 100)<br>${SCORE_COMPONENTS.map(([column,label])=>`${label}: ${num(row[column])===null?naText:d3.format('.2f')(num(row[column]))}`).join('<br>')}<br><br>${esc(row['Score breakdown'])}`;
}

function speciesNote(project) {
  const rows=(ORGANPIPE.species||[]).filter(row=>text(row['Project name'])===project&&row.Verdict);
  if(!rows.length)return '';
  return '<br>Species: '+rows.map(row=>{
    const identity=num(row['Identity to declared species (%)']);
    const verdict=text(row.Verdict);
    if(verdict==='Not declared')return `${esc(row.Marker)} closest to <em>${esc(text(row['Probable species']).split(';')[0])}</em>`;
    return `<span class="verdict-chip ${verdict.replace(/\s+/g,'-')}">${esc(verdict)}</span> ${esc(row.Marker)}${identity===null?'':` ${d3.format('.1f')(identity)}%`}`;
  }).join(', ');
}

function recommendedPicks() {
  const all=ORGANPIPE.scores||[];
  const projects=[...state.projects].filter(project=>all.some(row=>text(row['Project name'])===project)).sort((a,b)=>a.localeCompare(b,undefined,{numeric:true}));
  return projects.map(project=>{
    const ranked=all.filter(row=>text(row['Project name'])===project).sort((a,b)=>num(a['Rank in project'],1e9)-num(b['Rank in project'],1e9));
    const inView=ranked.filter(matches);
    const overall=ranked.find(row=>row.Recommended===true);
    const pick=overall&&inView.includes(overall)?overall:inView.find(row=>row.Eligible===true);
    return {project,ranked,inView,overall,pick};
  });
}

const PATH_KINDS=['Pilon FASTA','Rotated GenBank','GenBank'];
function renderRecommendedPaths(picks) {
  const kind=(document.querySelector('input[name="pathKind"]:checked')||{}).value||'Pilon FASTA';
  const kinds=kind==='all'?PATH_KINDS:[kind];
  const lines=[], missing=[];
  picks.filter(item=>item.pick).forEach(({project,pick})=>{
    kinds.forEach(column=>{
      const path=text(pick[column]).trim();
      if(path)lines.push(path); else missing.push(`${project} (${column})`);
    });
  });
  const area=document.getElementById('recommendedPaths');
  area.value=lines.join('\n');
  area.rows=Math.max(3,Math.min(12,lines.length));
  const note=document.getElementById('recommendedPathsNote');
  const projects=picks.filter(item=>item.pick).length;
  note.textContent=`${lines.length} path${lines.length===1?'':'s'} for ${projects} project${projects===1?'':'s'} with a recommended assembly in the current filters.`
    +(missing.length?` Not found on disk when the report was built: ${missing.join(', ')}.`:'')
    +(picks.some(item=>!item.pick)?` ${picks.filter(item=>!item.pick).length} project(s) have no circularized assembly to recommend.`:'');
}

function renderRecommendation() {
  const cards=document.getElementById('recommendationCards');
  const all=ORGANPIPE.scores||[];
  const subtitle=document.getElementById('recommendationSubtitle');
  const picks=recommendedPicks();
  if(!all.length||!picks.length){
    subtitle.textContent='No assembly score for this run (it needs the OrganPipe quality analyses).';
    cards.innerHTML='';document.getElementById('rankingBody').innerHTML='';document.getElementById('rankingHead').innerHTML='';
    document.getElementById('recommendedPaths').value='';
    document.getElementById('recommendation').style.display=all.length?'':'none';
    return;
  }
  document.getElementById('recommendation').style.display='';
  subtitle.textContent='The highest-scoring circularized assembly of each project. Copy the files of the recommended assemblies below, open the cards for the score of each pick, or the full ranking for every assembly. The score ranks, it does not discard: check the alerts of the chosen assembly before keeping it.';
  renderRecommendedPaths(picks);
  document.getElementById('recommendationCount').textContent=`· ${picks.filter(item=>item.pick).length} of ${picks.length} projects`;
  cards.innerHTML=picks.map(({project,ranked,inView,overall,pick})=>{
    const eligible=ranked.filter(row=>row.Eligible===true).length;
    const cls=!pick?'no-pick':(pick===overall?'':'hidden-pick');
    const location=locationText(projectRecord(project));
    if(!pick)return `<div class="card reco-card no-pick"><div class="reco-project">${projectDisplayHtml(projectRecord(project))}${location?` · ${esc(location)}`:''}</div><div class="reco-meta">No circularized assembly ${overall?'in the current filters':'in this project'}. ${ranked.length} assemblies were scored.</div></div>`;
    const runnerUp=inView.filter(row=>row!==pick&&row.Eligible===true)[0];
    const weights=(ORGANPIPE.settings_phase2||{}).score_weights||{};
    const naValue=(ORGANPIPE.settings_phase2||{}).score_na_value;
    const bars=SCORE_COMPONENTS.map(([column,label,key])=>{
      const value=num(pick[column]);
      return `<div class="reco-metric"><div class="reco-metric-head"><span class="reco-metric-name">${esc(label)}</span><span class="reco-metric-weight">weight ${esc(weights[key]??'—')}</span><span class="reco-metric-value">${value===null?`NA${naValue===null||naValue===undefined?'':` (${naValue})`}`:d3.format('.2f')(value)}</span></div>`
        +`<span class="reco-bar ${value===null?'na':''}"><span style="width:${value===null?0:Math.round(100*value)}%"></span></span>`
        +`<div class="reco-metric-help">${esc(scoreComponentHelp(key))}</div></div>`;
    }).join('');
    const alerts=(ORGANPIPE.alerts||[]).filter(row=>text(row.Assembly)===text(pick.Assembly)).map(row=>row['Alert type']);
    return `<div class="card reco-card ${cls}" data-assembly="${esc(pick.Assembly)}">
      <div class="reco-info">
        <div class="reco-project">${projectDisplayHtml(projectRecord(project))}${location?` <span class="table-count">· ${esc(location)}</span>`:''}</div>
        <div class="reco-assembly">${esc(pick['Seed Input'])} · K-mer ${esc(pick['K-mer'])} · copy _${esc(pick['Assembly copy'])}</div>
        <div class="reco-meta">${pick===overall?'Recommended':'Best in the current filters; the overall pick ('+esc(overall?`${overall['Seed Input']} · k${overall['K-mer']} · _${overall['Assembly copy']}`:'none')+') is filtered out'} · ${eligible} of ${ranked.length} assemblies circularized${runnerUp?` · next: ${esc(runnerUp['Seed Input'])} · k${esc(runnerUp['K-mer'])} (${fmtNum(runnerUp.Score,'.1f')})`:''}${alerts.length?`<br>Alerts: ${esc([...new Set(alerts)].join(', '))}`:''}${speciesNote(project)}</div>
      </div>
      <div class="reco-score">${fmtNum(pick.Score,'.1f')}<small> / 100</small><div class="reco-score-note">weighted mean of the components × 100 <span class="info-dot" data-tooltip-html="${esc(scoreBreakdownHtml(pick))}">i</span></div></div>
      <div class="reco-components">${bars}</div>
    </div>`;
  }).join('');

  const weights=(ORGANPIPE.settings_phase2||{}).score_weights||{};
  document.getElementById('rankingWeights').textContent=`Weights: ${SCORE_COMPONENTS.map(([,label,key])=>`${label} ${weights[key]??'—'}`).join(' · ')} (assembly_score.weights in config.yml). NA components count as ${(ORGANPIPE.settings_phase2||{}).score_na_value??'not counted'} (assembly_score.na_value).`;
  const rows=all.filter(matches).sort((a,b)=>text(a['Project name']).localeCompare(text(b['Project name']),undefined,{numeric:true})||num(a['Rank in project'],0)-num(b['Rank in project'],0));
  document.getElementById('rankingCount').textContent=`· ${rows.length} assemblies`;
  const helpHead=(label,help)=>`<th data-help="${esc(help)}" class="help-head">${esc(label)}</th>`;
  document.getElementById('rankingHead').innerHTML=`<tr><th>Project / species</th><th>Location</th>${helpHead('Rank','Position of the assembly within its project. Circularized assemblies rank above the others; ★ marks the recommended one.')}<th>Seed · K-mer · copy</th>${helpHead('Circular','Whether NOVOPlasty closed the assembly into a circle. Only circularized assemblies can be recommended.')}${helpHead('Score','Weighted mean of the components × 100. The weights are listed above the table.')}${SCORE_COMPONENTS.map(([,label,key])=>helpHead(label,scoreComponentHelp(key))).join('')}</tr>`;
  document.getElementById('rankingBody').innerHTML=rows.map(row=>`<tr class="${row.Recommended===true?'recommended':''}" data-assembly="${esc(row.Assembly)}"><td style="text-align:left">${projectDisplayHtml(projectRecord(row['Project name']))}</td><td style="text-align:left">${esc(locationText(projectRecord(row['Project name'])))}</td><td>${esc(row['Rank in project'])}${row.Recommended===true?' ★':''}</td><td>${esc(row['Seed Input'])} · k${esc(row['K-mer'])} · _${esc(row['Assembly copy'])}</td><td class="${row.Circularized===true?'':'table-count'}">${row.Circularized===true?'Yes':'No'}</td><td><strong>${fmtNum(row.Score,'.1f')}</strong></td>${SCORE_COMPONENTS.map(([column])=>{const value=num(row[column]);return `<td class="component-cell">${value===null?'NA':d3.format('.2f')(value)}<div class="reco-bar ${value===null?'na':''}"><span style="width:${value===null?0:Math.round(100*value)}%"></span></div></td>`;}).join('')}</tr>`).join('');
  pinColumns(document.getElementById('rankingTable'),2);
}

function initRecommendedPaths() {
  document.querySelectorAll('input[name="pathKind"]').forEach(input=>input.addEventListener('change',()=>renderRecommendedPaths(recommendedPicks())));
  const button=document.getElementById('copyRecommendedPaths');
  button.addEventListener('click',async()=>{
    const area=document.getElementById('recommendedPaths');
    const label=button.querySelector('span');
    let copied=false;
    try{ await navigator.clipboard.writeText(area.value); copied=true; }
    catch(error){ area.focus(); area.select(); try{ copied=document.execCommand('copy'); }catch(inner){ copied=false; } }
    label.textContent=copied?'Copied':'Select and copy (Ctrl+C)';
    button.classList.toggle('copied',copied);
    if(!copied){ area.focus(); area.select(); }
    setTimeout(()=>{ label.textContent='Copy paths'; button.classList.remove('copied'); },1800);
  });
}

function renderProvenance() {
  const body=document.getElementById('provenanceBody');
  const rows=ORGANPIPE.provenance||[];
  const benchmarks=(ORGANPIPE.benchmarks||[]).filter(row=>state.projects.has(text(row['Project name'])));
  if(!rows.length&&!benchmarks.length){body.innerHTML='<div class="table-count">Provenance was disabled for this run.</div>';return;}
  const groups=d3Group(rows,row=>text(row.Category));
  const table=(items,cols)=>`<div class="table-scroll" style="max-height:420px"><table class="assembly-table${cols[0]==='Project name'?' pin-first':''}"><thead><tr>${cols.map(c=>`<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${items.map(item=>`<tr>${cols.map(c=>`<td>${esc(item[c])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  body.innerHTML=[...groups.entries()].map(([category,items])=>`<h3 style="margin:16px 0 6px;font-size:14px">${esc(category)}</h3>${table(items,['Item','Value'])}`).join('')
    +(benchmarks.length?`<h3 style="margin:16px 0 6px;font-size:14px">OrganPipe benchmarks</h3>${table(benchmarks,['Project name','Rule','Runs','Wall time (s)','CPU time (s)','Max RSS (MB)'])}`:'<h3 style="margin:16px 0 6px;font-size:14px">OrganPipe benchmarks</h3><div class="table-count">No Snakemake benchmark files were found.</div>');
  body.querySelectorAll('table.pin-first').forEach(table=>pinColumns(table,1));
}

// ---------------- Phase 3: heteroplasmy, NCBI validation, species and RefSeq ----------------
const PHASE3=ORGANPIPE.settings_phase3||{};
function projectRows(key){return (ORGANPIPE[key]||[]).filter(row=>state.projects.has(text(row['Project name'])));}
function runLabel(row){return `${esc(row['Seed Input'])} · k${esc(row['K-mer'])} · _${esc(row['Assembly copy'])}`;}
function recommendedAssemblies(){return new Set((ORGANPIPE.scores||[]).filter(row=>row.Recommended===true).map(row=>text(row.Assembly)));}

function renderHeteroplasmy() {
  const showLow=document.getElementById('heteroplasmyShowLow').checked;
  const query=text(document.getElementById('heteroplasmySearch').value).trim().toLowerCase();
  const summary=organpipeRows('heteroplasmy');
  const all=organpipeRows('heteroplasmy_sites');
  const rows=sortAssemblyRows(all.filter(row=>showLow||text(row.Confidence)==='high')
    .filter(row=>!query||[projectDisplayText(projectRecord(row['Project name'])),row['Project name'],row['Seed Input'],`k${text(row['K-mer'])}`,row.Region,row.Position,row.Reason].map(text).join(' ').toLowerCase().includes(query)))
    .sort((a,b)=>text(a['Project name']).localeCompare(text(b['Project name']),undefined,{numeric:true})||text(a.Assembly).localeCompare(text(b.Assembly))||num(a.Position,0)-num(b.Position,0));
  const settings=PHASE3.heteroplasmy||{};
  const high=all.filter(row=>text(row.Confidence)==='high');
  const withSites=new Set(high.map(row=>text(row.Assembly))).size;
  const qualities=summary.some(row=>text(row['Base qualities']).startsWith('absent'))?' Base qualities are absent from the BAMs, so bases were not filtered by quality.':'';
  document.getElementById('heteroplasmyCount').textContent=!ORGANPIPE.heteroplasmy
    ? 'Heteroplasmy was not run.'
    : `${summary.length} assemblies scanned · ${high.length} high-confidence sites in ${withSites} assemblies · ${all.length-high.length} low-confidence · depth ≥ ${text(settings.min_depth??20)}, minor base ≥ ${text(settings.min_minor_reads??3)} reads and ≥ ${d3.format('.0%')(num(settings.min_frequency,.1))}.${qualities}`;
  const columns=['Project / species','Location','Seed · K-mer · copy','Position','Region','Depth','Change','Minor frequency','Minor reads (+ / −)','Confidence','Why low'];
  document.getElementById('heteroplasmyHead').innerHTML=`<tr>${columns.map(c=>`<th>${esc(c)}</th>`).join('')}</tr>`;
  const shown=rows.slice(0,1500);
  document.getElementById('heteroplasmyBody').innerHTML=shown.map(row=>{
    const frequency=num(row['Minor frequency'],0);
    return `<tr><td style="text-align:left">${projectDisplayHtml(projectRecord(row['Project name']))}</td><td style="text-align:left">${esc(locationText(projectRecord(row['Project name'])))}</td><td>${runLabel(row)}</td><td class="q-num">${d3.format(',')(num(row.Position,0))}</td><td><strong>${esc(row.Region)}</strong></td><td class="q-num">${d3.format(',')(num(row.Depth,0))}</td><td><code>${esc(row['Major base'])}&gt;${esc(row['Minor base'])}</code></td>`
      +`<td class="data-bar-cell q-num" style="--bar-width:${Math.min(100,200*frequency).toFixed(1)}%;--bar-color:rgba(204,120,188,.35)"><div class="cell-bar"></div><span class="cell-value">${d3.format('.1%')(frequency)}</span></td>`
      +`<td>${esc(row['Minor reads forward'])} / ${esc(row['Minor reads reverse'])}</td><td class="${text(row.Confidence)==='high'?'q-warn':''}">${esc(row.Confidence)}</td><td style="text-align:left;white-space:normal;min-width:220px">${esc(row.Reason)}</td></tr>`;
  }).join('')+(rows.length>shown.length?`<tr><td colspan="${columns.length}" class="table-count">${rows.length-shown.length} more rows in heteroplasmy/heteroplasmy_sites.tsv</td></tr>`:'')
    || `<tr><td colspan="${columns.length}" class="table-count" style="padding:16px">${summary.length?'No candidate site for the current filters.':'No BAM was found for the assemblies in view.'}</td></tr>`;
  pinColumns(document.getElementById('heteroplasmyTable'),2);
}

function renderValidation() {
  const rows=sortAssemblyRows(organpipeRows('validation'));
  const messages=sortAssemblyRows(organpipeRows('validation_messages'));
  const blocking=row=>num(row.Rejects,0)+num(row.Errors,0)+num(row['Fatal discrepancies'],0);
  document.getElementById('validationCount').textContent=!(ORGANPIPE.validation||[]).length
    ? 'table2asn was not run (disabled, not installed, or no GenBank in view).'
    : `${rows.length} assemblies checked · ${rows.filter(row=>blocking(row)).length} with rejects, errors or FATAL discrepancies · ${d3.sum(rows,row=>num(row['Incomplete stops completed'],0))} incomplete stop codons completed in the feature tables`;
  const columns=['Project / species','Location','Seed · K-mer · copy','Organism used','Rejects','Errors','Warnings','FATAL','Discrepancies','Stops completed','Main issues','Submission files'];
  document.getElementById('validationHead').innerHTML=`<tr>${columns.map(c=>`<th>${esc(c)}</th>`).join('')}</tr>`;
  const countCell=(value,bad)=>`<td class="q-num ${num(value,0)?(bad?'q-bad':'q-warn'):'q-ok'}">${esc(value)}</td>`;
  document.getElementById('validationBody').innerHTML=rows.map(row=>`<tr><td style="text-align:left">${projectDisplayHtml(projectRecord(row['Project name']))}</td><td style="text-align:left">${esc(locationText(projectRecord(row['Project name'])))}</td><td>${runLabel(row)}</td><td><em>${esc(row.Organism)}</em></td>${countCell(row.Rejects,true)}${countCell(row.Errors,true)}${countCell(row.Warnings,false)}${countCell(row['Fatal discrepancies'],true)}${countCell(row.Discrepancies,false)}<td class="q-num">${esc(row['Incomplete stops completed'])}</td><td style="text-align:left;white-space:normal;min-width:200px">${esc(row['Main issues'])||'<span class="table-count">none</span>'}</td><td style="text-align:left"><code class="path-code">${esc(row['Output folder'])}</code></td></tr>`).join('')
    || `<tr><td colspan="${columns.length}" class="table-count" style="padding:16px">No checked assembly for the current filters.</td></tr>`;
  document.getElementById('validationMessagesSummary').textContent=`Messages (${messages.length})`;
  const messageColumns=['Project / species','Seed · K-mer · copy','Source','Severity','Code','Message','Location'];
  const severityClass={reject:'q-bad',fatal:'q-bad',error:'q-bad',warning:'q-warn',discrepancy:'q-warn',info:''};
  document.getElementById('validationMessagesHead').innerHTML=`<tr>${messageColumns.map(c=>`<th>${esc(c)}</th>`).join('')}</tr>`;
  document.getElementById('validationMessagesBody').innerHTML=messages.slice(0,1500).map(row=>`<tr><td style="text-align:left">${projectDisplayHtml(projectRecord(row['Project name']))}</td><td>${runLabel(row)}</td><td>${esc(row.Source)}</td><td class="${severityClass[text(row.Severity)]||''}">${esc(row.Severity)}</td><td><code>${esc(row.Code)}</code></td><td style="text-align:left;white-space:normal;min-width:320px">${esc(row.Message)}</td><td>${esc(row.Location)}</td></tr>`).join('')
    || `<tr><td colspan="${messageColumns.length}" class="table-count" style="padding:16px">No message: the checked annotations are ready for submission.</td></tr>`;
  pinColumns(document.getElementById('validationTable'),2);
}

function speciesHitList(hits,declared,database) {
  if(!hits.length)return '<span class="sp-empty">no hit above the minimum overlap</span>';
  const low=Math.min(85,d3.min(hits,hit=>num(hit['Identity (%)'],100))-1);
  const sameSpecies=(a,b)=>text(a).split(/\s+/).slice(0,2).join(' ').toLowerCase()===text(b).split(/\s+/).slice(0,2).join(' ').toLowerCase();
  return `<div class="sp-list">${hits.map(hit=>{
    const identity=num(hit['Identity (%)'],0);
    const record=text(hit['Best record']);
    const url=database==='BOLD'?`https://portal.boldsystems.org/record/${encodeURIComponent(record)}`:`https://www.ncbi.nlm.nih.gov/nuccore/${encodeURIComponent(record)}`;
    const tip=`${hit.Species}: ${d3.format('.2f')(identity)}% identity over ${d3.format(',')(num(hit['Overlap (bp)'],0))} bp; ${hit.Records} record(s) above the minimum overlap; best record ${record}${text(hit.BIN)?` (${hit.BIN})`:''}${text(hit.Title)?`. ${hit.Title}`:''}`;
    return `<div class="sp-hit ${declared&&sameSpecies(hit.Species,declared)?'declared':''}" data-tooltip="${esc(tip)}"><span class="sp-rank">${esc(hit.Rank)}</span><a href="${url}" target="_blank" rel="noopener"><em>${esc(hit.Species)}</em></a><span class="reco-bar"><span style="width:${Math.max(2,100*(identity-low)/(100-low)).toFixed(1)}%"></span></span><span class="sp-id">${d3.format('.2f')(identity)}%</span></div>`;
  }).join('')}</div>`;
}

function renderSpeciesId() {
  const rows=projectRows('species').sort((a,b)=>text(a['Project name']).localeCompare(text(b['Project name']),undefined,{numeric:true}));
  const hits=projectRows('species_hits');
  const remote=PHASE3.remote||{};
  const settings=PHASE3.species||{};
  const section=document.getElementById('species');
  const subtitle=document.getElementById('speciesSubtitle');
  const ran=(ORGANPIPE.species||[]).length||(ORGANPIPE.reference||[]).length;
  section.style.display=ran||remote.offline?'':'none';
  subtitle.textContent=remote.offline
    ? 'NCBI could not be reached when the report was built, so species identification and the RefSeq comparison were skipped.'
    : `${text(PHASE3.organelle||'mitochondrion')} · ${PHASE3.metadata_species?'species declared in the metadata are checked':'no metadata: the most similar species of each database are listed'} · species ranked by identity over at least ${text(settings.min_overlap??400)} bp, confirmation at ${text(settings.identity_threshold??97)}% · ${text(remote.rate??3)} requests per second${remote.api_key?' (NCBI API key)':''} · ${num(remote.requests,0)?`${text(remote.requests)} requests to NCBI and BOLD${num(remote.failures,0)?`, ${remote.failures} failed`:''}`:'all answers read from the cache'} (species_identification/cache).`;
  const verdicts=d3.rollup(rows,v=>v.length,row=>text(row.Verdict));
  document.getElementById('speciesCount').textContent=rows.length?[...verdicts].map(([key,value])=>`${value} ${key.toLowerCase()}`).join(' · '):'';
  const columns=['Project / species','Location','Marker (assembly)','Verdict','Identity to declared','BOLD: most similar species','GenBank: most similar species','Taxonomy (NCBI)'];
  document.getElementById('speciesHead').innerHTML=`<tr>${columns.map(c=>`<th>${esc(c)}</th>`).join('')}</tr>`;
  document.getElementById('speciesBody').innerHTML=rows.map(row=>{
    const project=text(row['Project name']);
    const list=database=>hits.filter(hit=>text(hit['Project name'])===project&&text(hit.Marker)===text(row.Marker)&&text(hit.Database)===database).sort((a,b)=>num(a.Rank,0)-num(b.Rank,0));
    const declared=text(row['Declared species']);
    const identity=num(row['Identity to declared species (%)']);
    const verdict=text(row.Verdict);
    const assembly=(ORGANPIPE.scores||[]).find(item=>text(item.Assembly)===text(row.Assembly));
    const lineage=['Genus','Family','Order','Class'].map(rank=>text(row[rank])).filter(Boolean).join(' · ');
    return `<tr><td style="text-align:left">${projectDisplayHtml(projectRecord(project))}${declared?'':' <span class="table-count">(no declared species)</span>'}</td><td style="text-align:left">${esc(locationText(projectRecord(project)))}</td>`
      +`<td style="text-align:left"><strong>${esc(row.Marker)}</strong> <span class="table-count">${row['Marker length']?d3.format(',')(num(row['Marker length'],0))+' bp':''}</span><br><span class="table-count">${assembly?runLabel(assembly):esc(row.Assembly)}</span></td>`
      +`<td><span class="verdict-chip ${verdict.replace(/\s+/g,'-')}">${esc(verdict)}</span></td>`
      +`<td class="q-num">${identity===null?'—':`<strong>${d3.format('.2f')(identity)}%</strong>`}${[['BOLD','Declared species identity in BOLD (%)'],['GenBank','Declared species identity in GenBank (%)']].map(([name,column])=>num(row[column])===null?(declared?`<br><span class="table-count">${name}: not found</span>`:''):`<br><span class="table-count">${name}: ${d3.format('.2f')(num(row[column]))}%${name==='GenBank'&&row['Declared species GenBank record']?` (${esc(row['Declared species GenBank record'])})`:''}</span>`).join('')}</td>`
      +`<td>${text(row['BOLD status'])==='failed'?'':speciesHitList(list('BOLD'),declared,'BOLD')}${text(row['BOLD status'])==='failed'?'<span class="sp-empty" data-tooltip="The BOLD search failed (no network, or BOLD busy). Run moCURA again: answers already received are read from the cache.">BOLD did not answer; run again to retry</span>':''}</td>`
      +`<td>${text(row['GenBank status'])==='failed'?'':speciesHitList(list('GenBank'),declared,'GenBank')}${text(row['GenBank status'])==='failed'?'<span class="sp-empty" data-tooltip="The NCBI BLAST search failed or did not finish within blast_max_wait (config.yml). Run moCURA again: answers already received are read from the cache.">GenBank BLAST did not answer; run again to retry</span>':''}</td>`
      +`<td style="text-align:left;white-space:normal;min-width:160px">${esc(lineage)||'—'}${row['Taxonomy species']?`<br><span class="table-count">from ${esc(row['Taxonomy species'])}</span>`:''}</td></tr>`;
  }).join('') || `<tr><td colspan="${columns.length}" class="table-count" style="padding:16px">No species identification for the current filters.</td></tr>`;
  pinColumns(document.getElementById('speciesTable'),2);
}

let referenceMetric='length';
function renderReferenceStrip() {
  const container=document.getElementById('referenceStrip');
  clearChart('referenceStrip');
  const assemblies=organpipeRows('reference');
  const genomes=projectRows('reference_genomes');
  const settings=PHASE3.reference||{};
  const subtitle=document.getElementById('referenceSubtitle');
  if(!assemblies.length){subtitle.textContent='No RefSeq comparison for the current filters.';return;}
  const length=referenceMetric==='length';
  const value=row=>num(row[length?'Genome length':'Bases in repeats']);
  const refValue=row=>num(row[length?'Genome length':'Bases in repeats']);
  const tolerance=length?num(settings.length_tolerance_percent,5)/100:0;
  const recommended=recommendedAssemblies();
  const projects=[...new Set(assemblies.map(row=>text(row['Project name'])))].sort((a,b)=>a.localeCompare(b,undefined,{numeric:true}));
  const outside=assemblies.filter(row=>length?['Shorter','Longer'].includes(text(row['Genome length status'])):['More repeats','Fewer repeats'].includes(text(row['Repeat status']))).length;
  subtitle.textContent=`${assemblies.length} assemblies of ${projects.length} sample(s) compared with ${new Set(genomes.map(row=>text(row.Accession))).size} RefSeq genomes · ${outside} outside the reference range${length?` (± ${d3.format('~g')(100*tolerance)}%)`:''}.`;
  const values=[...assemblies.map(value),...genomes.map(refValue)].filter(v=>v!==null);
  if(!values.length){emptyChart('referenceStrip','No value to compare (TRF may be disabled).');return;}
  const labels=projects.map(project=>{const first=assemblies.find(row=>text(row['Project name'])===project);return `${projectDisplayText(projectRecord(project))} · ${text(first['Reference level'])} ${text(first['Reference taxon'])} (${text(first.References)})`;});
  const labelWidth=Math.min(420,Math.max(220,svgLabelWidth(labels,10.5)+24));
  const width=Math.max(760,container.clientWidth||1100);
  const rowHeight=40, top=12, bottom=34;
  const height=top+projects.length*rowHeight+bottom;
  const svg=d3.select('#referenceStrip').append('svg').attr('width',width).attr('height',height).attr('viewBox',`0 0 ${width} ${height}`);
  let [low,high]=d3.extent(values);
  const pad=Math.max(1,(high-low)*.08);
  let domain=[low-pad,high+pad];
  // Genome length: keep the scale around the references; partial contigs far from them sit at the edge.
  const refAll=genomes.map(refValue).filter(v=>v!==null);
  if(length&&refAll.length){
    const [refLow,refHigh]=d3.extent(refAll);
    domain=[Math.max(domain[0],refLow*.85),Math.min(domain[1],refHigh*1.15)];
  }
  const x=d3.scaleLinear().domain(domain).nice().range([labelWidth,width-18]);
  const [xMin,xMax]=x.domain();
  svg.append('g').attr('class','grid-line').attr('transform',`translate(0,${top})`).call(d3.axisTop(x).ticks(8).tickSize(-(projects.length*rowHeight)).tickFormat(''));
  svg.append('g').attr('class','axis').attr('transform',`translate(0,${top+projects.length*rowHeight})`).call(d3.axisBottom(x).ticks(8).tickFormat(d3.format(',')));
  svg.append('text').attr('x',(labelWidth+width-18)/2).attr('y',height-4).attr('text-anchor','middle').attr('font-size',10.5).attr('fill','#64748b').text(length?'Genome length (bp)':'Bases in tandem repeats (TRF)');
  projects.forEach((project,index)=>{
    const y=top+index*rowHeight+rowHeight/2;
    const rows=assemblies.filter(row=>text(row['Project name'])===project);
    const refs=genomes.filter(row=>text(row['Project name'])===project);
    const first=rows[0];
    const label=svg.append('text').attr('x',labelWidth-10).attr('y',y+4).attr('text-anchor','end').attr('font-size',10.5).attr('fill','#0f172a');
    setSvgProjectLabel(label,projectRecord(project),{suffix:` · ${text(first['Reference level'])} ${text(first['Reference taxon'])} (${text(first.References)})`});
    if(index)svg.append('line').attr('x1',8).attr('x2',width-18).attr('y1',y-rowHeight/2).attr('y2',y-rowHeight/2).attr('stroke','#e2e8f0');
    const refValues=refs.map(refValue).filter(v=>v!==null);
    if(refValues.length){
      const [a,b]=d3.extent(refValues);
      svg.append('rect').attr('x',x(a*(1-tolerance))).attr('y',y-11).attr('width',Math.max(2,x(b*(1+tolerance))-x(a*(1-tolerance)))).attr('height',22).attr('rx',4).attr('fill','#029E73').attr('fill-opacity',.12);
    }
    rows.forEach((row,i)=>{
      const v=value(row); if(v===null)return;
      const status=length?text(row['Genome length status']):text(row['Repeat status']);
      const pick=recommended.has(text(row.Assembly));
      const off=pick?0:((i%5)-2)*3.2;
      const clipped=v<xMin?'left':(v>xMax?'right':null);
      const mark=clipped
        ? svg.append('path').attr('d',d3.symbol(d3.symbolTriangle,pick?90:42)()).attr('transform',`translate(${clipped==='left'?x(xMin)+5:x(xMax)-5},${y+off}) rotate(${clipped==='left'?-90:90})`)
        : svg.append('circle').attr('cx',x(v)).attr('cy',y+off).attr('r',pick?6:3.6);
      mark
        .attr('fill',['Within'].includes(status)?'#029E73':(status==='NA'?'#94a3b8':'#DE8F05')).attr('fill-opacity',pick?1:.7)
        .attr('stroke',pick?'#0f172a':'#fff').attr('stroke-width',pick?1.6:.6)
        .on('mousemove',event=>hover(event,`<b>${esc(projectDisplayText(projectRecord(project)))}</b> · ${runLabel(row)}${pick?' (recommended)':''}${clipped?'<br>Outside the scale of the chart (triangle at the edge)':''}<br>${length?`${d3.format(',')(v)} bp · references ${d3.format(',')(num(row['Reference length min'],0))}–${d3.format(',')(num(row['Reference length max'],0))} bp`:`${d3.format(',')(v)} bp in ${esc(row['Tandem repeats'])} repeats · references ${d3.format(',')(num(row['Reference bases in repeats min'],0))}–${d3.format(',')(num(row['Reference bases in repeats max'],0))} bp`}<br>${esc(status)}`)).on('mouseleave',unhover);
    });
    refs.forEach(ref=>{
      const v=refValue(ref); if(v===null)return;
      svg.append('path').attr('d',d3.symbol(d3.symbolDiamond,70)()).attr('transform',`translate(${x(v)},${y})`).attr('fill','#475569').attr('stroke','#fff').attr('stroke-width',.8)
        .on('mousemove',event=>hover(event,`<b><i>${esc(ref.Organism)}</i></b> · ${esc(ref.Accession)} (RefSeq)<br>${d3.format(',')(num(ref['Genome length'],0))} bp · ${esc(ref.Genes)} genes · ${ref['Tandem repeats']===null||ref['Tandem repeats']===undefined?'TRF not run':`${esc(ref['Tandem repeats'])} tandem repeats, ${d3.format(',')(num(ref['Bases in repeats'],0))} bp`}`)).on('mouseleave',unhover);
    });
  });
}

function renderReferenceList() {
  const rows=projectRows('reference_genomes').sort((a,b)=>text(a['Project name']).localeCompare(text(b['Project name']),undefined,{numeric:true})||text(a.Accession).localeCompare(text(b.Accession)));
  document.getElementById('referenceListSummary').textContent=`RefSeq genomes used (${new Set(rows.map(row=>text(row.Accession))).size} genomes for ${new Set(rows.map(row=>text(row['Project name']))).size} samples)`;
  const columns=['Project / species','Level','Taxon','Accession','Organism','Genome length','Genes','Tandem repeats','Bases in repeats'];
  document.getElementById('referenceListHead').innerHTML=`<tr>${columns.map(c=>`<th>${esc(c)}</th>`).join('')}</tr>`;
  document.getElementById('referenceListBody').innerHTML=rows.map(row=>`<tr><td style="text-align:left">${projectDisplayHtml(projectRecord(row['Project name']))}</td><td>${esc(row['Reference level'])}</td><td><em>${esc(row['Reference taxon'])}</em></td><td><a href="https://www.ncbi.nlm.nih.gov/nuccore/${encodeURIComponent(text(row.Accession))}" target="_blank" rel="noopener">${esc(row.Accession)}</a></td><td style="text-align:left"><em>${esc(row.Organism)}</em></td><td class="q-num">${d3.format(',')(num(row['Genome length'],0))}</td><td class="q-num">${esc(row.Genes)}</td><td class="q-num">${esc(row['Tandem repeats']??'—')}</td><td class="q-num">${row['Bases in repeats']===null||row['Bases in repeats']===undefined?'—':d3.format(',')(num(row['Bases in repeats'],0))}</td></tr>`).join('')
    || `<tr><td colspan="${columns.length}" class="table-count" style="padding:16px">No RefSeq genome for the current filters.</td></tr>`;
  pinColumns(document.getElementById('referenceListTable'),1);
}

function renderPhase3() {
  renderHeteroplasmy();
  renderValidation();
  renderSpeciesId();
  renderReferenceStrip();
  renderReferenceGenes();
  renderReferenceList();
}

function renderOrganpipeSections() {
  renderRecommendation();
  renderIntegrityTable();
  renderConcordance();
  renderComposition();
  renderQualityGuide();
  renderReadQc();
  renderCompletenessHeatmap();
  renderQualityTable();
  renderPhase3();
  renderProvenance();
}

function markerCategory(markerName) {
  const raw=text(markerName).trim();
  const normalized=raw.toUpperCase().replace(/[^A-Z0-9]/g,'');
  if(/^TRNA/.test(normalized)||/^TRN[A-Z]/.test(normalized)||raw.toLowerCase().startsWith('trna'))return 'tRNAs';
  if(['12S','16S','23S','45S','5S','RRNS','RRNL','12SRRNA','16SRRNA'].includes(normalized)||normalized.includes('RRNA')||/^RRN[0-9]/.test(normalized))return 'rRNAs';
  if(/^(DLOOP|CONTROL|OH|OL|IGS|INTERGENIC|REPEAT|LSC|SSC)/.test(normalized))return 'Other';
  // Every other annotated marker is a protein-coding gene (mitochondrial or plastid).
  return 'PCGs';
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

let snpIncludeIncomplete=false;
const SNP_MISSING='·';
const completenessByRunCopy=new Map((ORGANPIPE.completeness||[]).map(row=>[[text(row['Project name']).trim(),text(row['Seed Input']).trim(),normalizedRunValue(row['K-mer']),normalizedRunValue(row['Assembly copy'])].join('\0'),row]));

function numOrNull(value) {
  if(value===null||value===undefined||text(value).trim()==='')return null;
  return num(value);
}

function snpRunRow(row) {
  return {'Project name':row.project,'Seed Input':row.seed,'K-mer':row.kmer};
}

function snpRowCircular(row) {
  const summary=summaryByRunKey.get(rowKey(snpRunRow(row)));
  return summary?summary.Circularized===true:null;
}

function snpRowMatches(row) {
  if (!state.projects.size || !state.projects.has(text(row.project))) return false;
  if (!state.seed.size || !state.seed.has(text(row.seed))) return false;
  if (!state.kmer.size || !state.kmer.has(text(row.kmer))) return false;
  const circular=snpRowCircular(row);
  const status=circular===false?'Not circularized':'Circularized';
  if (!state.status.has(status)) return false;
  const hasRepeat = repeatRunKeys.has(rowKey(snpRunRow(row)));
  const repeatStatus = hasRepeat ? 'With repeats' : 'Without repeats';
  if (!state.repeats.size || !state.repeats.has(repeatStatus)) return false;
  return true;
}

function snpMedianLength(matrix) {
  return median(matrix.rows.map(row=>numOrNull(row.ungapped_length)).filter(value=>value!==null&&value>0));
}

// Reasons why a sequence can distort the matrix: an open (non-circularized) assembly,
// a marker much shorter than the others, or a gene MITOS2 only found as a fragment.
function snpRowIssues(matrix,row,medianLength) {
  const issues=[];
  if(snpRowCircular(row)===false)issues.push('assembly not circularized');
  const length=numOrNull(row.ungapped_length);
  const ratio=num(REPORT_CONFIG.snp_min_length_ratio,0.9);
  if(length!==null&&medianLength&&length<ratio*medianLength)issues.push(`marker has ${d3.format(',')(length)} bp, ${Math.round(100*length/medianLength)}% of the median ${d3.format(',')(Math.round(medianLength))} bp`);
  const completeness=completenessByRunCopy.get([text(row.project).trim(),text(row.seed).trim(),normalizedRunValue(row.kmer),normalizedRunValue(row.assembly_copy)].join('\0'));
  const status=completeness?text(completeness[matrix.marker]):'';
  if(status==='Partial at origin')issues.push('MITOS2 kept only a fragment of this gene at the contig origin');
  if(status==='Absent')issues.push('MITOS2 did not annotate this gene');
  return issues;
}

// States outside the first..last aligned base of a sequence are missing data, not deletions.
function snpRowStates(row) {
  const first=numOrNull(row.first_column), last=numOrNull(row.last_column);
  return row.states.map((state,index)=>{
    const column=numOrNull((row.alignment_columns||[])[index]);
    if(first!==null&&last!==null&&column!==null&&(column<first||column>last))return SNP_MISSING;
    return text(state||'N').toUpperCase();
  });
}

// A sequence that disagrees with the majority at most SNP columns, while the others
// rarely do, is often a different region (misannotation) rather than real variation.
function snpDivergenceWarnings(display) {
  const warnings=new Map();
  const columns=display.positions.length;
  if(columns<5||display.rows.length<3)return warnings;
  const canonical=new Set(['A','C','G','T']);
  const majority=display.positions.map((_,index)=>{
    const counts=d3.rollup(display.rows.map(row=>row.displayStates[index]).filter(base=>canonical.has(base)),values=>values.length,base=>base);
    return [...counts.entries()].sort((a,b)=>b[1]-a[1])[0]?.[0]||null;
  });
  const shares=display.rows.map(row=>{
    let compared=0,different=0;
    row.displayStates.forEach((base,index)=>{ if(!canonical.has(base)||!majority[index])return; compared++; if(base!==majority[index])different++; });
    return {row,share:compared?different/compared:0};
  });
  const typical=median(shares.map(item=>item.share))||0;
  shares.forEach(({row,share})=>{
    if(share>=.5&&share>=typical+.3)warnings.set(row.sequence_id,[`differs from the majority at ${Math.round(100*share)}% of the SNP columns; check whether the same region was extracted`]);
  });
  return warnings;
}

// Keep only the columns that still vary among the displayed sequences.
function buildDisplayedSnpMatrix(matrix,rows,referenceId) {
  const canonical=new Set(['A','C','G','T']);
  const statesById=new Map(rows.map(row=>[row.sequence_id,snpRowStates(row)]));
  const keep=matrix.positions.map((_,index)=>new Set(rows.map(row=>statesById.get(row.sequence_id)[index]).filter(base=>canonical.has(base))).size>=2);
  const indices=keep.map((value,index)=>value?index:-1).filter(index=>index>=0);
  const labels=referencePositionLabels(matrix,referenceId);
  return {
    marker:matrix.marker,
    positions:indices.map(index=>matrix.positions[index]),
    labels:indices.map(index=>labels[index]),
    rows:rows.map(row=>({...row,displayStates:indices.map(index=>statesById.get(row.sequence_id)[index])})),
    referenceId,
    alignment_length:numOrNull(matrix.alignment_length),
    allColumns:matrix.positions.length
  };
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
  const entries = [['A','A'],['C','C'],['G','G'],['T','T'],['-','gap'],['N','N'],[SNP_MISSING,'sequence ends']];
  const legend = svg.append('g').attr('transform',`translate(${startX},${y})`);
  let x=0;
  entries.forEach(([base,label])=>{
    legend.append('rect').attr('x',x).attr('y',-10).attr('width',15).attr('height',15).attr('rx',2).attr('fill',snpBaseColors[base]).attr('stroke',base===SNP_MISSING?'#94a3b8':'none').attr('stroke-dasharray',base===SNP_MISSING?'2,2':null);
    legend.append('text').attr('x',x+20).attr('y',2).attr('font-size',10).attr('fill','#475569').text(label);
    x+=label.length*6+34;
  });
  return {legend,width:x};
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

function snpLengthBar(svg,x,y,width,row,alignmentLength,flagged) {
  const first=numOrNull(row.first_column), last=numOrNull(row.last_column);
  if(first===null||last===null||!alignmentLength)return;
  svg.append('rect').attr('x',x).attr('y',y).attr('width',width).attr('height',5).attr('rx',2.5).attr('fill','#e2e8f0');
  svg.append('rect').attr('x',x+width*(first-1)/alignmentLength).attr('y',y).attr('width',Math.max(2,width*(last-first+1)/alignmentLength)).attr('height',5).attr('rx',2.5).attr('fill',flagged?'#DE8F05':'#029E73');
}

function renderSnpPanel(container, display, panel, panelIndex, panelCount, context) {
  const labelWidth = 300;
  const rowHeight = 28;
  const containerWidth=Math.max(480,(container.clientWidth||900)-16);
  const matrixX = labelWidth + 16;
  const panelPositions=display.labels.slice(panel.start,panel.end);
  const fitCell=(containerWidth-matrixX-16)/Math.max(1,panelPositions.length);
  const cellWidth=Math.max(30,Math.min(64,fitCell));
  const matrixWidth = panelPositions.length*cellWidth;
  const width=Math.max(containerWidth,matrixX+matrixWidth+16);
  const referenceId=display.referenceId;
  const displayedRows = sortSnpRows(display.rows, referenceId);
  const referenceRow=displayedRows.find(row=>row.sequence_id===referenceId)||displayedRows[0]||{};

  // Marker track (reference coordinates) on top, with connectors fanning down to the columns.
  const barY=64, barHeight=14;
  const connectorTop=barY+barHeight+24, labelBase=connectorTop+62;
  const topSpace=labelBase+10;
  const barX=matrixX, barWidth=width-matrixX-16;
  const allParsed=display.labels.map(parseReferencePosition);
  const referenceLength=numOrNull(referenceRow.ungapped_length)||numOrNull(referenceRow.marker_length)||d3.max(allParsed,item=>item.base)||1;
  const markerScale=d3.scaleLinear().domain([1,Math.max(2,referenceLength)]).range([barX,barX+barWidth]).clamp(true);
  const markerStart=numOrNull(referenceRow.marker_start), markerEnd=numOrNull(referenceRow.marker_end);

  // Every row has the same height; a line (not a gap) separates projects.
  let previousProject = null;
  const rowLayout = displayedRows.map((row,index)=>{
    const isReference = row.sequence_id === referenceId;
    const newProject = !isReference && previousProject !== null && text(row.project) !== text(previousProject);
    if(!isReference) previousProject = row.project;
    return {row,index,y:topSpace+index*rowHeight,isReference,newProject};
  });
  const height = topSpace + displayedRows.length*rowHeight + 14;
  const svg = d3.select(container).append('svg').attr('width',width).attr('height',height).attr('viewBox',`0 0 ${width} ${height}`);

  svg.append('text').attr('x',10).attr('y',20).attr('font-size',12).attr('font-weight',700).attr('fill','#0f172a').text(panelCount>1?`Panel ${panelIndex+1} of ${panelCount} · columns ${panel.start+1}–${panel.end}`:'SNP positions');
  svg.append('text').attr('x',10).attr('y',36).attr('font-size',10).attr('fill','#64748b').text(`${displayedRows.length} sequences · ${panelPositions.length} SNP columns`);
  const snpLegend=drawSnpLegend(svg,0,0);
  snpLegend.legend.attr('transform',`translate(${Math.max(320,width-snpLegend.width-12)},24)`);

  // Marker bar
  svg.append('text').attr('x',10).attr('y',barY+10).attr('font-size',10.5).attr('font-weight',700).attr('fill','#334155').text(`${display.marker} in the reference`);
  svg.append('text').attr('x',10).attr('y',barY+24).attr('font-size',9.3).attr('fill','#64748b').text(markerStart!==null&&markerEnd!==null?`${d3.format(',')(referenceLength)} bp · genome ${d3.format(',')(markerStart)}–${d3.format(',')(markerEnd)} bp`:`${d3.format(',')(referenceLength)} bp`);
  svg.append('rect').attr('x',barX).attr('y',barY).attr('width',barWidth).attr('height',barHeight).attr('rx',4).attr('fill','#e0f2fe').attr('stroke','#7dd3fc');
  allParsed.forEach((parsed,index)=>{
    if(parsed.base===null)return;
    const inPanel=index>=panel.start&&index<panel.end;
    if(inPanel)return;
    const x=markerScale(Math.max(1,parsed.base));
    svg.append('line').attr('x1',x).attr('x2',x).attr('y1',barY+2).attr('y2',barY+barHeight-2).attr('stroke','#94a3b8').attr('stroke-width',1);
  });
  const axis=d3.axisBottom(markerScale).ticks(Math.max(2,Math.floor(barWidth/110))).tickFormat(value=>d3.format(',')(value)).tickSizeOuter(0);
  svg.append('g').attr('class','axis').attr('transform',`translate(0,${barY+barHeight})`).call(axis);

  panelPositions.forEach((position,j)=>{
    const parsed=parseReferencePosition(position);
    const colX=matrixX+j*cellWidth+(cellWidth-2)/2;
    if(parsed.base!==null){
      const x=markerScale(Math.max(1,parsed.base));
      svg.append('path').attr('d',`M${x},${barY+barHeight} C${x},${connectorTop+20} ${colX},${connectorTop+16} ${colX},${connectorTop+36}`).attr('fill','none').attr('stroke','#64748b').attr('stroke-opacity',.55).attr('stroke-width',1);
      svg.append('line').attr('x1',x).attr('x2',x).attr('y1',barY-3).attr('y2',barY+barHeight+3).attr('stroke','#1d4ed8').attr('stroke-width',1.6)
        .on('mousemove',event=>hover(event,`<b>${esc(display.marker)}</b><br>Reference position ${esc(displayReferencePosition(position))}${markerStart!==null?`<br>Approx. genome coordinate ${d3.format(',')(markerStart+Math.max(0,parsed.base-1))} bp`:''}`)).on('mouseleave',unhover);
    }
    svg.append('text').attr('x',colX).attr('y',labelBase).attr('text-anchor','start').attr('transform',`rotate(-60,${colX},${labelBase})`).attr('font-size',9).attr('fill','#334155').text(displayReferencePosition(position));
  });

  rowLayout.forEach(layout=>{
    const background = layout.isReference ? '#dbeafe' : (layout.index%2===0 ? '#f1f5f9' : '#ffffff');
    svg.append('rect').attr('x',0).attr('y',layout.y).attr('width',width).attr('height',rowHeight).attr('fill',background);
  });
  rowLayout.filter(layout=>layout.newProject||layout.index===1).forEach(layout=>{
    svg.append('line').attr('x1',0).attr('x2',width).attr('y1',layout.y).attr('y2',layout.y).attr('stroke',layout.index===1?'#93c5fd':'#94a3b8').attr('stroke-width',1);
  });

  rowLayout.forEach(layout=>{
    const row = layout.row;
    const y = layout.y;
    const labelRow={project:row.project,species:row.species};
    const issues=context.issues.get(row.sequence_id)||[];
    const labelSubParts = [`Seed ${text(row.seed)}`, `K-mer ${text(row.kmer)}`];
    if(text(row.location)) labelSubParts.push(text(row.location));
    const labelSelection=svg.append('text').attr('x',10).attr('y',y+12.5).attr('font-size',10.3).attr('fill','#0f172a');
    setSvgProjectLabel(labelSelection,labelRow,{prefix:layout.isReference?'Reference · ':'',suffix:issues.length?'  ⚠':''});
    svg.append('text').attr('x',10).attr('y',y+24).attr('font-size',9).attr('fill','#64748b').text(labelSubParts.join(' · '));
    snpLengthBar(svg,labelWidth-74,y+19,70,row,display.alignment_length,issues.length>0);
    const rowInfo=`${layout.isReference?'<strong>Reference</strong><br>':''}${projectDisplayHtml(labelRow)}<br>${esc(labelSubParts.join(' · '))}${numOrNull(row.ungapped_length)!==null?`<br>Marker sequence: ${d3.format(',')(row.ungapped_length)} bp`:''}${issues.length?`<br><b>Check:</b> ${esc(issues.join('; '))}`:''}`;
    svg.append('rect').attr('x',0).attr('y',y).attr('width',labelWidth).attr('height',rowHeight).attr('fill','transparent').on('mousemove',event=>hover(event,rowInfo)).on('mouseleave',unhover);

    panelPositions.forEach((position,j)=>{
      const base = row.displayStates[panel.start+j] || 'N';
      const x = matrixX+j*cellWidth;
      const missing=base===SNP_MISSING;
      svg.append('rect').attr('x',x).attr('y',y+3).attr('width',cellWidth-2).attr('height',rowHeight-6).attr('rx',3).attr('fill',snpBaseColors[base] || '#cbd5e1').attr('stroke',missing?'#94a3b8':'#ffffff').attr('stroke-width',missing?0.8:0.6).attr('stroke-dasharray',missing?'2,2':null)
        .on('mousemove',event=>hover(event,`${rowInfo}<br>Reference position: ${esc(displayReferencePosition(position))}<br>State: ${missing?'no data (the sequence ends before this position)':esc(base)}`))
        .on('mouseleave',unhover);
      if(!missing)svg.append('text').attr('x',x+(cellWidth-2)/2).attr('y',y+rowHeight/2+4).attr('text-anchor','middle').attr('font-size',10).attr('font-weight',700).attr('fill','#111827').attr('pointer-events','none').text(base);
    });
  });
}

function renderSnpMatrices() {
  const gallery=document.getElementById('snpGallery');
  gallery.innerHTML='';

  const matrices=REPORT.snp_matrices||[];
  const columnsPerPanel=Math.max(1,num(REPORT_CONFIG.snp_columns_per_panel,60));
  let rendered=0, hiddenTotal=0;

  matrices.forEach(matrix=>{
    const medianLength=snpMedianLength(matrix);
    const issues=new Map(matrix.rows.map(row=>[row.sequence_id,snpRowIssues(matrix,row,medianLength)]));
    const clean=row=>!(issues.get(row.sequence_id)||[]).length;
    let referenceId=selectedSnpReferenceId(matrix);
    if(!snpIncludeIncomplete&&!snpReferenceSelection.has(matrix.marker)){
      const reference=matrix.rows.find(row=>row.sequence_id===referenceId);
      if(reference&&!clean(reference)){
        const replacement=matrix.rows.find(clean);
        if(replacement)referenceId=replacement.sequence_id;
      }
    }
    const filtered=matrix.rows.filter(snpRowMatches);
    const hidden=snpIncludeIncomplete?[]:filtered.filter(row=>!clean(row)&&row.sequence_id!==referenceId);
    let rows=filtered.filter(row=>snpIncludeIncomplete||clean(row)||row.sequence_id===referenceId);
    hiddenTotal+=hidden.length;
    const reference=matrix.rows.find(row=>row.sequence_id===referenceId);
    if(rows.length&&reference&&!rows.some(row=>row.sequence_id===reference.sequence_id))rows=[reference,...rows];
    if(rows.length<2)return;

    const display=buildDisplayedSnpMatrix(matrix,rows,referenceId);
    if(!display.positions.length)return;
    const warnings=snpDivergenceWarnings(display);

    const card=document.createElement('div');
    card.className='card snp-card';
    gallery.appendChild(card);
    const title=document.createElement('div');
    title.className='snp-card-head';
    const options=matrix.rows.map(row=>`<option value="${esc(row.sequence_id)}" ${row.sequence_id===referenceId?'selected':''}>${esc(snpReferenceLabel(row))}${(issues.get(row.sequence_id)||[]).length?' (check)':''}</option>`).join('');
    const columnNote=display.positions.length===display.allColumns?'':` (${display.allColumns} when every sequence is included)`;
    title.innerHTML=`<div><div class="snp-card-title">${esc(matrix.marker)}</div><div class="snp-card-meta">${display.positions.length} SNP column${display.positions.length===1?'':'s'} among ${rows.length} sequences${esc(columnNote)} · coordinates follow the selected reference</div></div><div class="snp-reference-control"><label>Reference</label><select aria-label="Reference for ${esc(matrix.marker)}">${options}</select></div>`;
    const select=title.querySelector('select');
    select.addEventListener('change',()=>{ snpReferenceSelection.set(matrix.marker,select.value); renderSnpMatrices(); renderSamplingMap(); });
    card.appendChild(title);

    const flaggedShown=rows.filter(row=>!clean(row)||warnings.has(row.sequence_id));
    const reasons=row=>[...(issues.get(row.sequence_id)||[]),...(warnings.get(row.sequence_id)||[])].join('; ');
    const noteItem=(row,reason)=>`<li>${projectDisplayHtml({project:row.project,species:row.species})} · ${esc(row.seed)} · k${esc(row.kmer)}: ${esc(reason)}</li>`;
    const addNote=(summary,items)=>{const note=document.createElement('details');note.className='snp-hidden-note';note.innerHTML=`<summary>${summary}</summary><ul>${items}</ul>`;card.appendChild(note);};
    if(hidden.length)addNote(`<b>${hidden.length} sequence${hidden.length===1?'':'s'} hidden</b> because ${hidden.length===1?'it':'they'} could create false SNPs. Open the list for the reasons.`,hidden.map(row=>noteItem(row,(issues.get(row.sequence_id)||[]).join('; '))).join(''));
    if(flaggedShown.length)addNote(`<b>⚠ ${flaggedShown.length} sequence${flaggedShown.length===1?'':'s'} shown with a warning.</b> Dashed cells are positions where the sequence ends, not deletions.`,flaggedShown.map(row=>noteItem(row,reasons(row))).join(''));

    const panels=splitSnpPositions({positions:display.positions},columnsPerPanel);
    panels.forEach((panel,index)=>{
      const scroll=document.createElement('div'); scroll.className='snp-chart-scroll'; card.appendChild(scroll);
      renderSnpPanel(scroll,display,panel,index,panels.length,{issues:new Map([...issues].map(([id,list])=>[id,[...list,...(warnings.get(id)||[])]]))});
    });
    rendered++;
  });

  document.getElementById('snpToolbarNote').textContent=snpIncludeIncomplete
    ? 'All sequences are shown; flagged ones carry ⚠ and a note under the marker title.'
    : (hiddenTotal?`${hiddenTotal} flagged sequence${hiddenTotal===1?' is':'s are'} hidden and the SNP columns were recomputed without ${hiddenTotal===1?'it':'them'}.`:'No sequence was flagged as incomplete in the current view.');
  document.getElementById('snpSubtitle').textContent=rendered
    ? `${rendered} marker${rendered===1?'':'s'} with SNPs among the displayed sequences. Only columns that still vary among the sequences shown are drawn. The bar above each matrix is the marker in the reference sequence; lines link each SNP to its position. The small bar next to each name shows how much of the alignment that sequence covers.`
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
    'Gene context label':230,'Consensus':210,'Integrity alerts':140
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
  let dragging=false,startX=0,startY=0,startLeft=0,startTop=0;
  container.addEventListener('mousedown',event=>{ if(event.button!==2)return; dragging=true; startX=event.clientX; startY=event.clientY; startLeft=container.scrollLeft; startTop=container.scrollTop; container.classList.add('dragging'); unhover(); event.preventDefault(); });
  window.addEventListener('mousemove',event=>{ if(!dragging)return; container.scrollLeft=startLeft-(event.clientX-startX); container.scrollTop=startTop-(event.clientY-startY); event.preventDefault(); });
  window.addEventListener('mouseup',event=>{ if(!dragging || event.button!==2)return; dragging=false; container.classList.remove('dragging'); });
  container.addEventListener('contextmenu',event=>event.preventDefault());
}

// Every table can be scrolled by holding the right mouse button and dragging.
const DRAG_HINT='<div class="assembly-table-help"><svg viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M8 7h8M8 17h8M5 12h14"></path><path d="m8 9-3 3 3 3M16 9l3 3-3 3"></path></svg><span>Hold the right mouse button and drag to scroll the table.</span></div>';
function enableTableDragScroll() {
  document.querySelectorAll('.table-scroll').forEach(enableRightButtonDragScroll);
  document.querySelectorAll('.table-card .table-toolbar').forEach(toolbar=>{
    if(!toolbar.querySelector('.assembly-table-help'))toolbar.insertAdjacentHTML('beforeend',DRAG_HINT);
  });
}

// Keep the first columns (species and location) in place while the table scrolls sideways.
// Tables inside a closed <details> have no width yet: pin them again when it opens.
document.addEventListener('toggle',event=>{
  if(!event.target.open)return;
  event.target.querySelectorAll('table').forEach(table=>{ if(table._pinCount)pinColumns(table,table._pinCount); });
},true);

function pinColumns(table, count) {
  if(!table||count<1)return;
  table._pinCount=count;
  const apply=()=>{
    if(!table.getClientRects().length)return;
    const headRows=[...table.querySelectorAll('thead tr')];
    const reference=headRows[headRows.length-1];
    if(!reference)return;
    const offsets=[];
    let left=0, column=0;
    for(const cell of reference.children){
      if(column>=count)break;
      offsets[column]=left; left+=cell.getBoundingClientRect().width; column+=cell.colSpan||1;
    }
    table.querySelectorAll('tr').forEach(row=>{
      let index=0;
      [...row.children].forEach(cell=>{
        const span=cell.colSpan||1;
        const pinned=span===1&&index<count&&offsets[index]!==undefined;
        cell.classList.toggle('pinned',pinned);
        cell.classList.toggle('pinned-last',pinned&&index===count-1);
        cell.style.left=pinned?`${offsets[index]}px`:'';
        index+=span;
      });
    });
  };
  requestAnimationFrame(apply);
}

// ---------------- tooltips (Tippy.js) ----------------
const TIPPY_CDNS=[
  ['https://cdnjs.cloudflare.com/ajax/libs/popper.js/2.11.8/umd/popper.min.js','https://cdnjs.cloudflare.com/ajax/libs/tippy.js/6.3.7/tippy-bundle.umd.min.js'],
  ['https://unpkg.com/@popperjs/core@2.11.8/dist/umd/popper.min.js','https://unpkg.com/tippy.js@6.3.7/dist/tippy-bundle.umd.min.js']
];
async function loadTippy() {
  if(window.tippy)return true;
  for(const [popper,tippyUrl] of TIPPY_CDNS){
    try{
      if(!window.Popper)await loadExternalScript(popper);
      await loadExternalScript(tippyUrl);
      if(window.tippy)return true;
    }catch(error){ console.warn(error.message); }
  }
  return false;
}

const TIPPY_BASE={theme:'mocura',allowHTML:true,maxWidth:380,appendTo:()=>document.body,zIndex:10000};
let cursorTip=null, cursorPoint={x:0,y:0}, cursorHtml='';
function cursorTooltip() {
  if(cursorTip||!window.tippy)return cursorTip;
  const anchor=document.createElement('span');
  anchor.setAttribute('aria-hidden','true');
  anchor.style.cssText='position:fixed;left:0;top:0;width:0;height:0;pointer-events:none';
  document.body.appendChild(anchor);
  cursorTip=tippy(anchor,{...TIPPY_BASE,trigger:'manual',placement:'right-start',offset:[0,16],arrow:false,duration:[80,0],hideOnClick:false,
    getReferenceClientRect:()=>({width:0,height:0,top:cursorPoint.y,bottom:cursorPoint.y,left:cursorPoint.x,right:cursorPoint.x,x:cursorPoint.x,y:cursorPoint.y}),
    popperOptions:{modifiers:[{name:'flip',options:{fallbackPlacements:['left-start','right-end','left-end']}},{name:'preventOverflow',options:{padding:8,altAxis:true}}]}});
  return cursorTip;
}

function initStaticTooltips() {
  if(window.tippy&&tippy.delegate){
    tippy.delegate(document.body,{...TIPPY_BASE,target:'[data-tooltip],[data-tooltip-html],[data-help]',delay:[60,0],
      content:reference=>reference.dataset.tooltipHtml
        || (reference.dataset.help?`<b>${esc(reference.textContent)}</b><br>${esc(reference.dataset.help)}`:esc(reference.dataset.tooltip||''))});
    return;
  }
  document.body.addEventListener('mouseover',event=>{
    const element=event.target.closest('[data-tooltip],[data-tooltip-html],[data-help]');
    if(!element)return;
    const content=element.dataset.tooltipHtml||(element.dataset.help?`<b>${esc(element.textContent)}</b><br>${esc(element.dataset.help)}`:esc(element.dataset.tooltip||''));
    hover(event,content);
    const move=moveEvent=>hover(moveEvent,content);
    element.addEventListener('mousemove',move);
    element.addEventListener('mouseleave',()=>{ unhover(); element.removeEventListener('mousemove',move); },{once:true});
  });
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

// ---------------------------------------------------------------- chart guides
// "How to read" cards: one per chart or table. Clicking the card opens an animated
// panel with a small schematic of the chart and what it shows, how to read it and
// what to look for. Animations replay on every opening and respect reduced motion.
const GUIDE_ICON='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z"></path><path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H20v3H6.5A2.5 2.5 0 0 1 4 20.5z"></path><path d="M9 7h7M9 11h5"></path></svg>';

function guideRect(x,y,w,h,fill,cls='g-pop',delay=0,extra='') { return `<rect class="${cls}" style="--d:${delay}ms" x="${x}" y="${y}" width="${w}" height="${h}" rx="2.5" fill="${fill}" ${extra}/>`; }

const GUIDE_ART={
  heatmap:()=>{
    const shades=['#dbeafe','#93c5fd','#60a5fa','#2563eb','#bfdbfe','#1d4ed8','#eff6ff'];
    let s='';
    for(let r=0;r<4;r++){ s+=guideRect(8,26+r*25,26,8,'#cbd5e1','g-fade',r*60); for(let c=0;c<7;c++) s+=guideRect(42+c*27,20+r*25,24,22,shades[(r*3+c*5)%7],'g-pop',(r*7+c)*28); }
    for(let c=0;c<7;c++) s+=guideRect(46+c*27,6,16,7,'#cbd5e1','g-fade',c*40);
    s+=`<rect class="g-ring" x="${42+4*27-3}" y="${20+2*25-3}" width="30" height="28" rx="4" fill="none" stroke="#DE8F05" stroke-width="2.5"/>`;
    s+=`<rect class="g-sweep-x" x="42" y="18" width="24" height="100" rx="3" fill="#0f172a" fill-opacity=".06"/>`;
    return s;
  },
  matrix:()=>{
    let s=''; const n=6, size=19, x0=70, y0=14;
    const group=i=>i<4?0:1;
    for(let r=0;r<n;r++){
      s+=guideRect(8,y0+r*size+6,group(r)?34:50,7,group(r)?'#D55E00':'#94a3b8','g-fade',r*70);
      for(let c=0;c<n;c++){
        const fill=r===c?'#0f172a':(group(r)===group(c)?(Math.abs(r-c)===1?'#1d4ed8':'#2563eb'):'#bfdbfe');
        s+=guideRect(x0+c*size,y0+r*size,size-2,size-2,fill,'g-pop',(r*n+c)*22);
      }
    }
    s+=`<rect class="g-ring" x="${x0-3}" y="${y0-3}" width="${4*size+4}" height="${4*size+4}" rx="4" fill="none" stroke="#029E73" stroke-width="2.4"/>`;
    s+=`<rect class="g-ring g-late" x="${x0+4*size-3}" y="${y0+4*size-3}" width="${2*size+4}" height="${2*size+4}" rx="4" fill="none" stroke="#D55E00" stroke-width="2.4"/>`;
    s+=`<g class="g-fade" style="--d:700ms"><rect x="${x0+n*size+12}" y="${y0}" width="9" height="${n*size-2}" rx="2" fill="url(#gGradBlue)"/><text x="${x0+n*size+25}" y="${y0+8}" font-size="8" fill="#64748b">100%</text><text x="${x0+n*size+25}" y="${y0+n*size-4}" font-size="8" fill="#64748b">min</text></g>`;
    return `<defs><linearGradient id="gGradBlue" x1="0" x2="0" y1="1" y2="0"><stop offset="0" stop-color="#eff6ff"/><stop offset="1" stop-color="#1d4ed8"/></linearGradient></defs>`+s;
  },
  strip:()=>{
    let s=''; const rows=[30,66,102];
    rows.forEach((y,i)=>{
      s+=guideRect(8,y-4,36,8,'#cbd5e1','g-fade',i*80);
      s+=`<line x1="52" x2="232" y1="${y}" y2="${y}" stroke="#e2e8f0"/>`;
      s+=`<rect class="g-growx" style="--d:${150+i*90}ms" x="${112+i*6}" y="${y-11}" width="${64-i*8}" height="22" rx="4" fill="#029E73" fill-opacity=".15"/>`;
      [124,150,166].forEach((cx,k)=>{ s+=`<g transform="translate(${cx+i*3},${y}) rotate(45)"><path class="g-pop" style="--d:${350+i*90+k*60}ms" d="M-4,-4h8v8h-8z" fill="#475569"/></g>`; });
      const dots=i===1?[[138,'#029E73'],[156,'#029E73'],[206,'#DE8F05']]:[[132,'#029E73'],[146,'#029E73'],[160,'#029E73']];
      dots.forEach(([cx,color],k)=>{ s+=`<circle class="g-slide" style="--d:${600+i*120+k*80}ms;--from:${-70+k*10}px" cx="${cx}" cy="${y+(k-1)*3}" r="${k===0?6:3.8}" fill="${color}" stroke="${k===0?'#0f172a':'#fff'}" stroke-width="${k===0?1.6:.6}"/>`; });
    });
    s+=`<circle class="g-ring" cx="206" cy="69" r="9" fill="none" stroke="#DE8F05" stroke-width="2"/>`;
    return s;
  },
  bars:()=>{
    let s=`<line x1="20" x2="232" y1="120" y2="120" stroke="#cbd5e1"/>`;
    [[62,48],[58,52],[86,30],[44,40],[70,66],[36,34]].forEach(([a,b],i)=>{
      const x=30+i*34;
      s+=`<rect class="g-grow" style="--d:${i*90}ms" x="${x}" y="${120-a}" width="13" height="${a}" rx="2" fill="#0173B2"/>`;
      s+=`<rect class="g-grow" style="--d:${i*90+60}ms" x="${x+14}" y="${120-b}" width="13" height="${b}" rx="2" fill="#DE8F05"/>`;
    });
    s+=`<rect class="g-ring" x="${30+2*34-3}" y="${120-86-3}" width="33" height="${86+6}" rx="4" fill="none" stroke="#0f172a" stroke-width="1.6"/>`;
    return s;
  },
  scatter:()=>{
    let s=`<rect class="g-growx" style="--d:0ms" x="20" y="38" width="212" height="30" fill="#B0E4CC" fill-opacity=".8"/><line x1="20" x2="232" y1="124" y2="124" stroke="#cbd5e1"/><line x1="20" x2="20" y1="10" y2="124" stroke="#cbd5e1"/>`;
    const colors=['#0173B2','#DE8F05','#029E73','#CC78BC','#CA9161'];
    [[40,52],[62,48],[84,100],[106,56],[128,58],[150,92],[172,50],[194,110],[216,54]].forEach(([x,y],i)=>{
      const color=colors[i%5];
      s+=i%2?`<g transform="translate(${x},${y})"><path class="g-pop" style="--d:${150+i*70}ms" d="M0,-5 L5,4 L-5,4 Z" fill="${color}" stroke="#202020" stroke-width=".6"/></g>`:`<circle class="g-pop" style="--d:${150+i*70}ms" cx="${x}" cy="${y}" r="5" fill="${color}" stroke="#202020" stroke-width=".6"/>`;
    });
    s+=`<circle class="g-ring" cx="84" cy="100" r="10" fill="none" stroke="#D55E00" stroke-width="2"/>`;
    return s;
  },
  tracks:()=>{
    let s='';
    const genes=[[0,22,'#0173B2'],[26,18,'#029E73'],[48,30,'#CC78BC'],[82,14,'#CA9161'],[100,26,'#56B4E9'],[130,20,'#0173B2'],[154,28,'#029E73']];
    [22,62,102].forEach((y,i)=>{
      s+=`<line class="g-growx" style="--d:${i*120}ms" x1="20" x2="232" y1="${y+9}" y2="${y+9}" stroke="#94a3b8" stroke-width="1.5"/>`;
      genes.forEach(([x,w,color],k)=>{ const shift=i===2&&k>3?6:0; s+=guideRect(26+x+shift,(k%3===1?y+12:y),w,9,color,'g-slide',200+i*120+k*50,''); });
      s+=`<rect class="g-pop" style="--d:${700+i*120}ms" x="${200}" y="${y+2}" width="${i===1?26:12}" height="14" rx="2" fill="#DE8F05"/>`;
      s+=`<g transform="translate(${90+i*30},${y-3})"><path class="g-pop" style="--d:${900+i*120}ms" d="M-4,-4 h8 l-4,6 z" fill="#D55E00"/></g>`;
    });
    s+=`<rect class="g-ring" x="195" y="58" width="38" height="24" rx="4" fill="none" stroke="#DE8F05" stroke-width="2"/>`;
    return s;
  },
  table:()=>{
    let s=guideRect(10,8,222,14,'#e2e8f0','g-fade',0);
    const fills=[['#e7f6ef','#e7f6ef','#fff4e0','#ffffff'],['#e7f6ef','#fde8e4','#ffffff','#e7f6ef'],['#e7f6ef','#e7f6ef','#e7f6ef','#ffffff'],['#fff4e0','#e7f6ef','#ffffff','#fde8e4']];
    fills.forEach((row,r)=>{
      const y=26+r*24;
      s+=guideRect(10,y,70,20,r%2?'#EEEEEE':'#ffffff','g-fade',80+r*90,'stroke="#e2e8f0"');
      s+=guideRect(16,y+7,44,6,'#94a3b8','g-fade',100+r*90);
      row.forEach((fill,c)=>{ s+=guideRect(82+c*38,y,36,20,fill,'g-pop',140+r*90+c*45,'stroke="#e2e8f0"'); });
    });
    s+=`<rect class="g-sweep-y" x="8" y="24" width="226" height="24" rx="4" fill="none" stroke="#0173B2" stroke-width="2"/>`;
    return s;
  },
  stack:()=>{
    let s=`<line x1="18" x2="232" y1="92" y2="92" stroke="#cbd5e1"/>`;
    const colors=['#0173B2','#DE8F05','#029E73','#CC78BC'];
    [[1.6,.9,.8,.7],[2.2,1.8],[1.1,1,.9,1],[2.6,.8,.4,.2],[1.3,.7]].forEach((stack,i)=>{
      let base=92; const x=26+i*42;
      stack.forEach((value,k)=>{ const h=value*14; s+=`<rect class="g-grow" style="--d:${i*110+k*70}ms" x="${x}" y="${base-h}" width="30" height="${h}" fill="${colors[k]}" stroke="#fff" stroke-width=".6"/>`; base-=h; });
      s+=`<line class="g-fade" style="--d:${600+i*60}ms" x1="${x-2}" x2="${x+32}" y1="${92-stack.length*14}" y2="${92-stack.length*14}" stroke="#0f172a" stroke-dasharray="3,2" stroke-opacity=".6"/>`;
      s+=guideRect(x,96,30,9,'#e2e8f0','g-fade',500+i*60);
      stack.forEach((_,k)=>{ s+=guideRect(x,108+k*8,30,7,colors[k],'g-pop',650+i*60+k*40); });
    });
    return s;
  },
  snp:()=>{
    let s=''; const base={A:'#029E73',C:'#0173B2',G:'#DE8F05',T:'#D55E00'};
    const rows=['ACGTAC','ACGTAC','ATGTAC','ACGCAC','ATGTAG'];
    rows.forEach((row,r)=>{ s+=guideRect(8,16+r*22+5,40,8,'#cbd5e1','g-fade',r*60); [...row].forEach((nt,c)=>{ const differs=r>0&&nt!==rows[0][c]; s+=`<g class="g-pop" style="--d:${(r*6+c)*30}ms"><rect x="${60+c*28}" y="${16+r*22}" width="25" height="19" rx="3" fill="${differs?base[nt]:'#f1f5f9'}" stroke="#e2e8f0"/><text x="${72.5+c*28}" y="${29+r*22}" text-anchor="middle" font-size="10" font-weight="700" fill="${differs?'#fff':'#94a3b8'}">${nt}</text></g>`; }); });
    s+=`<rect class="g-ring" x="${60+28-3}" y="13" width="31" height="${5*22+2}" rx="4" fill="none" stroke="#0f172a" stroke-width="1.6"/>`;
    return s;
  },
  map:()=>{
    let s=`<path class="g-fade" d="M30,40 C60,10 120,18 150,30 C190,44 220,40 228,70 C236,104 190,124 140,118 C96,112 74,128 44,108 C20,92 14,62 30,40 Z" fill="#e2e8f0" stroke="#cbd5e1"/>`;
    [[80,60,'#0173B2',7],[120,82,'#DE8F05',5],[170,66,'#029E73',9],[104,100,'#0173B2',5]].forEach(([x,y,color,r],i)=>{ s+=`<circle class="g-pop" style="--d:${300+i*140}ms" cx="${x}" cy="${y}" r="${r}" fill="${color}" stroke="#fff" stroke-width="1.5"/>`; });
    s+=`<path class="g-draw" d="M80,60 L120,82 L170,66 M120,82 L104,100" fill="none" stroke="#475569" stroke-width="1.4" stroke-dasharray="160"/>`;
    s+=`<circle class="g-ring" cx="170" cy="66" r="14" fill="none" stroke="#029E73" stroke-width="2"/>`;
    return s;
  },
  list:()=>{
    let s='';
    [[0.95,'#05624b'],[0.83,'#029E73'],[0.78,'#029E73']].forEach(([w,color],i)=>{
      const y=22+i*34;
      s+=guideRect(10,y,14,10,'#cbd5e1','g-fade',i*90);
      s+=guideRect(30,y,90,10,i?'#94a3b8':color,'g-fade',i*90+60);
      s+=`<rect x="130" y="${y+1}" width="80" height="8" rx="4" fill="#e2e8f0"/><rect class="g-growx" style="--d:${250+i*140}ms" x="130" y="${y+1}" width="${80*w}" height="8" rx="4" fill="#029E73"/>`;
      s+=`<text class="g-fade" style="--d:${450+i*140}ms" x="214" y="${y+9}" font-size="9" fill="#334155">${(97.6-i*1.2).toFixed(1)}%</text>`;
    });
    s+=`<rect class="g-ring" x="6" y="17" width="232" height="20" rx="5" fill="none" stroke="#029E73" stroke-width="2"/>`;
    return s;
  },
  diverging:()=>{
    let s='';
    const values=[[0,0,0,0,0,0],[0,0,-3,0,0,0],[0,0,0,0,2,0],[0,-1,0,0,0,null],[0,0,0,0,0,0]];
    const color=v=>v===null?'url(#gHatch)':(v===0?'#ffffff':(v<0?(v<-2?'#0173B2':'#9ccbe6'):(v>1?'#DE8F05':'#f3c98b')));
    s+='<defs><pattern id="gHatch" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="4" fill="#f1f5f9"/><path d="M0,4 l4,-4" stroke="#94a3b8"/></pattern></defs>';
    for(let c=0;c<6;c++) s+=guideRect(52+c*30,6,22,7,'#94a3b8','g-fade',c*40);
    values.forEach((row,r)=>{ s+=guideRect(8,22+r*22+6,36,7,r===0?'#0f172a':'#cbd5e1','g-fade',r*60); row.forEach((v,c)=>{ s+=guideRect(50+c*30,20+r*22,27,19,color(v),'g-pop',(r*6+c)*26,'stroke="#e2e8f0"'); }); });
    s+=`<rect class="g-ring" x="${50+2*30-3}" y="${20+22-3}" width="33" height="25" rx="4" fill="none" stroke="#0f172a" stroke-width="1.6"/>`;
    return s;
  }
};

const GUIDES={
  recommendation:{art:'bars',summary:'Which assembly to keep for each sample, and why.',
    what:'For each sample, the circularized assembly with the highest score. The score adds seven components, each from 0 (worst) to 1 (best) multiplied by its weight in config.yml, and is shown out of 100.',
    read:['Each card is one sample: the recommended assembly, its score and one bar per component, with what the component measures.','NA components (for example no BAM for the junction) count as na_value in config.yml, 0.5 by default.','The full ranking lists every assembly of every sample with the same components, so you can see how close the runner-up is.','The file box gives the paths of the recommended assemblies, ready to copy.'],
    look:['A runner-up within a few points: both are equally good, choose by the alerts.','A recommended assembly with alerts in the Quality section: the score ranks, it does not discard.','A species verdict other than Confirmed on the card.']},
  assemblyPanels:{art:'scatter',summary:'The four NOVOPlasty statistics of every run, linked to each other.',
    what:'Number of contigs, largest and smallest contig, and average organelle coverage of every NOVOPlasty run (one point per project, seed and K-mer).',
    read:['Colour is the seed and shape is the K-mer (legend above).','The green band in the contig panels is the genome range of the NOVOPlasty configuration: a largest contig inside it is a candidate complete genome.','Click a point to keep the same run highlighted in the four panels; click it again to show all runs.'],
    look:['Runs with many contigs or a largest contig below the band: fragmented assembly.','Seeds or K-mers that fail for every sample.','Coverage far below the other runs of the same sample.']},
  assemblyTable:{art:'table',summary:'Every NOVOPlasty run with its status, contigs, coverage and Pilon metrics.',
    what:'One row per run with the values of the NOVOPlasty log and of Pilon.',
    read:['The first two columns stay visible while the table scrolls sideways.','The shaded bar inside a numeric cell is proportional to the largest value of its column.','Circularized is green when NOVOPlasty closed the genome into a circle.','The search box filters this table only.'],
    look:['Circularized runs whose largest contig differs from the other runs of the sample.','Runs with low coverage or few Pilon-confirmed bases.']},
  pilonMetrics:{art:'heatmap',summary:'Median Pilon statistics per project, each column on its own colour scale.',
    what:'Median coverage, confirmed bases and corrections of the Pilon runs of each project (of each seed when one project is selected).',
    read:['Each column has its own unit and colour scale, from its lowest to its highest value; the range is under the column title.','Darker means higher within that column only: do not compare colours across columns.','Tick "Show values in the cells" to print the numbers.'],
    look:['Low Confirmed %: Pilon could not confirm many bases with the reads.','Many corrected SNPs or indels compared with the other projects.']},
  pilonBeforeAfter:{art:'bars',summary:'Genome length before and after Pilon, median per project.',
    what:'The median length of the assemblies of each project before and after polishing.',
    read:['The two bars of a project are normally almost equal: Pilon changes few bases.','Hover a bar for the exact length.'],
    look:['A difference of more than a few base pairs: Pilon inserted or removed sequence, often inside repeats.']},
  pilonCorrections:{art:'bars',summary:'SNPs, insertions and deletions corrected by Pilon.',
    what:'The median number of corrections of each type per project.',
    read:['One group of bars per project; the colours are the correction types.'],
    look:['A project with many more corrections than the others: low coverage, read errors or mixed haplotypes.']},
  genome:{art:'tracks',summary:'Each rotated assembly as a linear map of genes, repeats, Pilon corrections and depth.',
    what:'Every rotated assembly in view drawn as a track, grouped by Seed + K-mer so the tracks of a group share the coordinate scale.',
    read:['Genes on the + strand are on the top line, genes on the − strand on the line below; the colour identifies the gene.','Orange blocks are TRF tandem repeats, labelled with their consensus.','Triangles mark Pilon corrections; the shaded profile is the read depth.'],
    look:['Genes shifted or missing compared with the other tracks of the sample.','Depth falling to almost zero: possible misassembly.','Repeats present only in some assemblies (often the control region).']},
  completeness:{art:'heatmap',summary:'Which expected genes the annotation found in each assembly.',
    what:'Presence of every expected gene in each assembly, read from the annotation (MITOS2 for mitochondria).',
    read:['Rows are assemblies, grouped by project and by Seed + K-mer (shaded blocks); columns are the expected genes.','Coloured cell: present. Empty: absent. Duplicated and "partial at origin" (only a fragment kept because the gene crosses the contig origin) have their own colours.','The last column compares the gene order with the most common order of the project.'],
    look:['A column with many empty cells: a gene the annotation often misses, frequently a tRNA.','A row with several genes absent: partial assembly.','"Differs" in the order column: rearrangement or misassembly.']},
  quality:{art:'table',summary:'One row per assembly copy with annotation, coverage, read, Pilon and junction checks.',
    what:'The checks of each assembly copy side by side, with a colour wherever a threshold applies.',
    read:['Green is within the expected range, orange is worth checking and red is a problem; uncoloured cells have no threshold, compare them across rows.','The first two columns stay visible while the table scrolls sideways.','Tick "Only assemblies with alerts" to shorten the table. The column definitions are below.'],
    look:['Red or orange cells in a recommended assembly.','Low coverage windows and unsupported junctions in the same assembly.'],
    extra:()=>'<div class="guide-columns-title">Columns</div><div id="qualityGuideBody" class="quality-guide-grid"></div>'},
  integrity:{art:'table',summary:'Every problem found in the annotated genes of the rotated GenBank.',
    what:'One row per gene and check: internal stop codons, reading frame, start and stop codons, genes crossing the origin and lengths far from the project mode.',
    read:['Error: blocks a GenBank submission. Warning: worth checking.','Informative rows (hidden by default) list incomplete stop codons that polyadenylation completes; they are normal in mitochondria.','Position is on the rotated genome.'],
    look:['Internal stop codons in a protein-coding gene: frameshift or annotation error.','The same issue in every assembly of a sample (biological or annotation) versus one assembly only (assembly error).']},
  concordance:{art:'matrix',summary:'How identical the assemblies of the same sample are to each other.',
    what:'Each card is one sample. Its rows and columns are the same assemblies, in the same order; each cell compares the assembly of its row with the assembly of its column after aligning the genomes with MAFFT.',
    read:['The colour of a cell is the identity (%) of the two genomes, without the gap columns. Darker blue is more identical; the scale on the right starts at the lowest identity of the sample, so small differences remain visible.','The black diagonal is each assembly compared with itself.','Assemblies whose identity and coverage are above the thresholds are linked into groups; the largest is the majority group, framed in green in the schematic. Labels in red are outside it, with their group number.','Hatched cells compared less than the minimum coverage: one genome is partial, so the identity is not meaningful.'],
    look:['A row and column lighter than the rest: an assembly that disagrees with the others (misassembly, contamination or another haplotype).','Two dark blocks along the diagonal: two groups that agree within but not between them.','Hatched cells: partial genomes, not real differences.']},
  heteroplasmy:{art:'list',summary:'Positions where the reads carry a second base.',
    what:'Sites of the rotated BAM where a minor base reaches the depth, read and frequency thresholds.',
    read:['High confidence: the minor base is on both strands, away from the contig ends, outside tandem repeats and not in a cluster of candidates.','Minor frequency is a lower bound: the BAM holds the reads NOVOPlasty assembled.','Tick "Show low-confidence sites" to see the rest, with the reason.'],
    look:['Several high-confidence sites in the same gene of different assemblies: real heteroplasmy, or a NUMT.','Many sites in a single assembly: contamination or mixed samples.']},
  validation:{art:'table',summary:'Whether the GenBank of each assembly passes the NCBI submission checks.',
    what:'The annotation converted into an NCBI submission (feature table with NCBI product names, incomplete stops completed) and validated with table2asn.',
    read:['Rejects, errors and FATAL discrepancies would block or delay the submission; warnings and other discrepancies are worth reading.','Stops completed counts the transl_except added for incomplete stop codons.','The folder holds the .sqn, .tbl, .fsa and .gbf files; open Messages for every message.'],
    look:['Any red cell in a recommended assembly before submitting it.']},
  species:{art:'list',summary:'Does the barcode of each sample match the declared species?',
    what:'The barcode (COI for mitochondria; rbcL and matK for chloroplasts) of the recommended assembly of each sample, searched in BOLD and in GenBank.',
    read:['Confirmed: the declared species reaches the identity threshold and no other species is clearly closer. Ambiguous: another species is closer. Not confirmed: below the threshold. No reference: neither database has the species. Not declared: no metadata.','The BOLD and GenBank columns list the three most similar species with their best identity; the declared species is in green.','Click a species to open its best record.'],
    look:['The declared species missing from the top three of both databases.','Several species within 1% of each other: the barcode does not separate them.','"did not answer": the search failed (network or a busy service); run moCURA again, answers already received come from the cache.']},
  referenceStrip:{art:'strip',summary:'Genome length or repeats of each sample against RefSeq genomes of its genus or family.',
    what:'One row per sample. Grey diamonds are RefSeq genomes of the genus of the sample (or of the family when the genus has none); circles are the assemblies in view.',
    read:['The green band is the reference range widened by the tolerance of config.yml.','Green circles are inside the band and orange circles outside; the large outlined circle is the recommended assembly.','For genome length the scale spans 15% around the references; partial contigs beyond it are triangles at the edge.'],
    look:['A recommended assembly outside the band: missing or duplicated region (often the control region).','A sample whose references are a different genus: the comparison is only approximate.']},
  referenceGenes:{art:'strip',summary:'Length of every gene against the same gene in the RefSeq genomes.',
    what:'One row per gene. The horizontal position is the difference from the median length of the gene in the RefSeq genomes, in percent; 0 is the median.',
    read:['Grey diamonds are the RefSeq genomes; the green band is their range widened by the gene tolerance of config.yml.','Circles are the assemblies (the recommended assembly of each sample, or every assembly in view): green inside the band, orange outside. The tooltip gives the lengths in bp.','On the right: the reference length range and how many assemblies fall outside it. "absent" lists assemblies without a gene that most references have.'],
    look:['Protein-coding genes outside the band: wrong start or stop, frameshift, or a truncated gene at the origin.','tRNAs and rRNAs vary more between annotators; check them against the alignment before editing.']},
  compositionStrip:{art:'strip',summary:'Base composition of each sample against the RefSeq genomes.',
    what:'GC content and skews of the assemblies and of the RefSeq genomes used in the comparison, one row per sample.',
    read:['Grey diamonds are RefSeq genomes and the green band is their range; circles are the assemblies in view, the outlined one is the recommended assembly.','AT skew = (A − T)/(A + T) and GC skew = (G − C)/(G + C), on the strand written in the GenBank file; PCG + and PCG − use the protein-coding genes of each strand read on their own coding strand.'],
    look:['An assembly far from the references and from the other assemblies of the sample: contamination, a NUMT or a strand inversion.']},
  rscu:{art:'stack',summary:'Codon usage of the protein-coding genes.',
    what:'Relative synonymous codon usage: how often each codon is used compared with its synonyms.',
    read:['Stacked view: one bar per codon box; each segment is one codon, in the colour and order of the boxes under the bar, with n = times counted. The dashed line is the height with no preference.','Heatmap view: one row per assembly and per RefSeq genome, one column per codon; red above 1 (preferred), blue below 1.','RefSeq genomes can also be chosen in the stacked view.'],
    look:['An assembly whose row differs from the others of its project and from the references: frameshifts or misannotated genes.']},
  compositionTable:{art:'table',summary:'GC content, skews and codons per assembly, with the RefSeq genomes below each sample.',
    what:'Composition of the whole genome and of the protein-coding genes by strand for each assembly; the grey rows are the RefSeq genomes compared with that sample.',
    read:['Compare each assembly with the RefSeq rows of its sample: GC % usually stays within a few points inside a genus.','Codons is the number of codons counted for the RSCU.'],
    look:['Differences much larger than among the references themselves.']},
  markers:{art:'diverging',summary:'Length of every marker in every assembly, coloured by its difference from the sample mode.',
    what:'One row per assembly copy, one column per marker. The number in a cell is the length of the marker in bp.',
    read:['The first row of each sample (bold) is its mode: the most common length of each marker in that sample. The RefSeq row, when present, is the median in the reference genomes.','White cells have the mode length. Blue cells are shorter and orange cells longer; the stronger the colour, the larger the difference. Hatched cells: marker not annotated.','Choose "Difference from the mode" to print +/− bp instead of the length, and tick the box to show only the assemblies that differ.'],
    look:['A column with many coloured cells: a marker whose boundaries vary between assemblies, often at the contig origin.','A single assembly with several coloured cells: likely misassembled.']},
  repeats:{art:'table',summary:'Every TRF tandem repeat with its position, gene context and consensus.',
    what:'One row per tandem repeat found by TRF in the assemblies in view.',
    read:['Bars inside the cells are proportional to the largest value in the column.','Context gives the genes around the repeat; the consensus is the repeated unit.'],
    look:['Repeats in the control region that differ in length between assemblies of the same sample: NOVOPlasty often collapses or expands them.']},
  snps:{art:'snp',summary:'Only the positions where the sequences of a marker differ.',
    what:'For every marker, the alignment of all assemblies in view reduced to the variable (SNP) positions.',
    read:['Each row is one sequence and each column a variable position; grey cells match the reference row, coloured cells differ (colour = base).','The reference row can be chosen per marker; position numbers are on that reference.','Incomplete or non-circularized sequences are hidden unless the box above is ticked.'],
    look:['Columns where one sample differs from the others: candidate population variation.','Rows with many differences: a divergent haplotype, or an assembly error.']},
  map:{art:'map',summary:'Sampling localities with the SNP differences of the selected markers.',
    what:'The localities of the metadata, with the number of SNP differences carried by the samples of each locality.',
    read:['Choose the markers that count in the panel above; the map and the network update.','The haplotype network joins unique haplotypes (circle size = number of sequences) with the number of differences on each link.'],
    look:['Haplotypes restricted to one locality, or shared across distant ones.']}
};

function guideHtml(key) {
  const guide=GUIDES[key];
  const art=(GUIDE_ART[guide.art]||GUIDE_ART.table)();
  const list=items=>`<ul>${items.map((item,index)=>`<li style="--i:${index}">${esc(item)}</li>`).join('')}</ul>`;
  return `<button type="button" class="guide-toggle" aria-expanded="false"><span class="guide-icon">${GUIDE_ICON}</span><span class="guide-label">How to read this</span><span class="guide-summary">${esc(guide.summary)}</span><span class="guide-chevron" aria-hidden="true"></span></button>`
    +`<div class="guide-panel" role="region"><div class="guide-inner"><div class="guide-body">`
    +`<div class="guide-art"><svg viewBox="0 0 240 140" role="img" aria-label="Schematic of the chart">${art}</svg></div>`
    +`<div class="guide-text"><div class="guide-block"><h4>What it shows</h4><p>${esc(guide.what)}</p></div><div class="guide-block"><h4>How to read it</h4>${list(guide.read)}</div><div class="guide-block"><h4>What to look for</h4>${list(guide.look)}</div></div>`
    +`</div>${guide.extra?`<div class="guide-extra">${guide.extra()}</div>`:''}</div></div>`;
}

function initChartGuides() {
  document.querySelectorAll('[data-guide]').forEach(host=>{
    if(host.dataset.guideReady)return;
    const key=host.dataset.guide;
    if(!GUIDES[key])return;
    host.dataset.guideReady='1';
    const card=document.createElement('div');
    card.className='guide-card';
    card.innerHTML=guideHtml(key);
    if(host.classList.contains('guide-slot')) host.appendChild(card);
    else if(host.tagName==='DETAILS') host.querySelector('summary').insertAdjacentElement('afterend',card);
    else if(host.querySelector(':scope > .table-toolbar')) host.querySelector(':scope > .table-toolbar').appendChild(card);
    else {
      const subtitle=host.querySelector(':scope > .chart-title ~ .chart-subtitle')||host.querySelector(':scope > .chart-title');
      (subtitle||host.firstElementChild).insertAdjacentElement('afterend',card);
    }
    const button=card.querySelector('.guide-toggle');
    const panel=card.querySelector('.guide-panel');
    button.addEventListener('click',()=>{
      const open=!panel.classList.contains('open');
      // Restart the animations on every opening.
      if(open){ panel.classList.remove('open'); void panel.offsetWidth; }
      panel.classList.toggle('open',open);
      card.classList.toggle('open',open);
      button.setAttribute('aria-expanded',String(open));
    });
  });
}

// ------------------------------------------------- RefSeq helpers (Phase 3, report)
// RefSeq genomes compared with each project, and their per-accession tables.
function referenceAccessionsByProject() {
  const map=new Map();
  (ORGANPIPE.reference_genomes||[]).forEach(row=>{
    const project=text(row['Project name']);
    if(!map.has(project))map.set(project,[]);
    if(!map.get(project).includes(text(row.Accession)))map.get(project).push(text(row.Accession));
  });
  return map;
}
const referenceCompositionByAccession=new Map((ORGANPIPE.reference_composition||[]).map(row=>[text(row.Accession),row]));
const referenceRscuByAccession=new Map((ORGANPIPE.reference_rscu||[]).map(row=>[text(row.Accession),row]));
function referenceGeneLengths() {
  const map=new Map();
  (ORGANPIPE.reference_gene_lengths||[]).forEach(row=>{
    const accession=text(row.Accession);
    if(!map.has(accession))map.set(accession,{organism:text(row.Organism),genes:new Map()});
    map.get(accession).genes.set(text(row.Marker),num(row.Length));
  });
  return map;
}

// Generic strip chart: one row per item, reference diamonds, a reference band and
// points (assemblies). Values beyond the domain are triangles at the edge.
function drawStripChart(id, options) {
  const container=document.getElementById(id);
  clearChart(id);
  const rows=options.rows||[];
  if(!rows.length){emptyChart(id,options.empty||'Nothing to compare for the current filters.');return;}
  const labelWidth=options.labelWidth||220;
  const rightWidth=options.rightWidth||0;
  const width=Math.max(760,container.clientWidth||1100);
  const rowHeight=options.rowHeight||34, top=options.axisTop?42:10, bottom=options.axisTop?10:38;
  const headerGap=18;
  let cursor=top;
  const layout=rows.map(row=>{ if(row.header){const item={row,y:cursor};cursor+=headerGap;return item;} const item={row,y:cursor+rowHeight/2};cursor+=rowHeight;return item; });
  const height=cursor+bottom;
  const svg=d3.select('#'+id).append('svg').attr('width',width).attr('height',height).attr('viewBox',`0 0 ${width} ${height}`);
  const x=d3.scaleLinear().domain(options.domain).range([labelWidth,width-rightWidth-16]);
  const [xMin,xMax]=x.domain();
  const plotBottom=cursor;
  svg.append('g').attr('class','grid-line').attr('transform',`translate(0,${top})`).call(d3.axisTop(x).ticks(8).tickSize(-(plotBottom-top)).tickFormat(''));
  if(options.zero!==undefined&&options.zero>=xMin&&options.zero<=xMax) svg.append('line').attr('x1',x(options.zero)).attr('x2',x(options.zero)).attr('y1',top).attr('y2',plotBottom).attr('stroke','#475569').attr('stroke-dasharray','3,3').attr('stroke-opacity',.6);
  const axis=options.axisTop?d3.axisTop(x):d3.axisBottom(x);
  svg.append('g').attr('class','axis').attr('transform',`translate(0,${options.axisTop?top:plotBottom})`).call(axis.ticks(8).tickFormat(options.tickFormat||d3.format(',')));
  if(options.axisLabel) svg.append('text').attr('x',(labelWidth+width-rightWidth-16)/2).attr('y',options.axisTop?11:height-4).attr('text-anchor','middle').attr('font-size',10.5).attr('fill','#64748b').text(options.axisLabel);
  const clipX=value=>value<xMin?'left':(value>xMax?'right':null);
  layout.forEach(({row,y},index)=>{
    if(row.header){
      svg.append('text').attr('x',8).attr('y',y+13).attr('font-size',10.5).attr('font-weight',800).attr('fill','#0173B2').text(row.header);
      svg.append('line').attr('x1',8).attr('x2',width-16).attr('y1',y+16).attr('y2',y+16).attr('stroke','#cbd5e1');
      return;
    }
    if(index&&!layout[index-1].row.header) svg.append('line').attr('x1',8).attr('x2',width-16).attr('y1',y-rowHeight/2).attr('y2',y-rowHeight/2).attr('stroke','#f1f5f9');
    const label=svg.append('text').attr('x',labelWidth-10).attr('y',y+4).attr('text-anchor','end').attr('font-size',10.5).attr('fill','#0f172a');
    row.label(label);
    (row.bands||[]).forEach(([a,b])=>{
      const left=x(Math.max(xMin,Math.min(xMax,a))), right=x(Math.max(xMin,Math.min(xMax,b)));
      svg.append('rect').attr('x',left).attr('y',y-rowHeight/2+5).attr('width',Math.max(3,right-left)).attr('height',rowHeight-10).attr('rx',4).attr('fill','#029E73').attr('fill-opacity',.13);
    });
    (row.refs||[]).forEach(ref=>{
      if(ref.value===null||ref.value===undefined||clipX(ref.value))return;
      svg.append('path').attr('d',d3.symbol(d3.symbolDiamond,64)()).attr('transform',`translate(${x(ref.value)},${y})`).attr('fill','#475569').attr('stroke','#fff').attr('stroke-width',.8)
        .on('mousemove',event=>hover(event,ref.tip)).on('mouseleave',unhover);
    });
    (row.points||[]).forEach((point,i)=>{
      if(point.value===null||point.value===undefined)return;
      const clipped=clipX(point.value);
      const off=point.pick?0:(((point.jitter??i)%5)-2)*Math.min(3.2,(rowHeight-14)/5);
      const mark=clipped
        ? svg.append('path').attr('d',d3.symbol(d3.symbolTriangle,point.pick?90:40)()).attr('transform',`translate(${clipped==='left'?x(xMin)+5:x(xMax)-5},${y+off}) rotate(${clipped==='left'?-90:90})`)
        : svg.append('circle').attr('cx',x(point.value)).attr('cy',y+off).attr('r',point.pick?6:3.6);
      mark.attr('fill',point.color||'#0173B2').attr('fill-opacity',point.pick?1:.72).attr('stroke',point.pick?'#0f172a':'#fff').attr('stroke-width',point.pick?1.6:.6)
        .on('mousemove',event=>hover(event,point.tip+(clipped?'<br>Beyond the scale of the chart (triangle at the edge)':''))).on('mouseleave',unhover);
      if(point.pick)mark.raise();
    });
    if(row.right) svg.append('text').attr('x',width-rightWidth-4).attr('y',y+4).attr('font-size',10).attr('fill',row.rightColor||'#64748b').text(row.right);
    if(row.absent){ const t=svg.append('text').attr('x',x((xMin+xMax)/2)).attr('y',y+4).attr('text-anchor','middle').attr('font-size',10).attr('fill','#94a3b8').text(row.absent); if(row.absentTip)t.on('mousemove',event=>hover(event,row.absentTip)).on('mouseleave',unhover); }
  });
}

// ----------------------------------------------- gene lengths against RefSeq (strip)
let referenceGenesScope='recommended';
let referenceGenesOnlyOutside=false;
const GENE_CLASS_ORDER=['PCGs','rRNAs','tRNAs','Other'];
function renderReferenceGenes() {
  const legend=document.getElementById('referenceGenesLegend');
  const settings=PHASE3.reference||{};
  const tolerance=num(settings.gene_tolerance_percent,10);
  const recommended=recommendedAssemblies();
  let rows=organpipeRows('reference_genes');
  if(referenceGenesScope==='recommended')rows=rows.filter(row=>recommended.has(text(row.Assembly)));
  const subtitle=document.getElementById('referenceGenesSubtitle');
  if(!rows.length){subtitle.textContent='No gene comparison for the current filters.';legend.innerHTML='';clearChart('referenceGenes');return;}
  const accessions=referenceAccessionsByProject();
  const lengths=referenceGeneLengths();
  const byMarker=d3.group(rows,row=>text(row.Marker));
  const expected=(ORGANPIPE.expected_markers||[]).map(text);
  const order=(a,b)=>{const ia=expected.indexOf(a), ib=expected.indexOf(b);return (ia<0?999:ia)-(ib<0?999:ib)||a.localeCompare(b,undefined,{numeric:true});};
  const outsideOf=items=>items.filter(row=>['Shorter','Longer','Absent'].includes(text(row.Status)));
  let markers=[...byMarker.keys()].sort(order);
  if(referenceGenesOnlyOutside)markers=markers.filter(marker=>outsideOf(byMarker.get(marker)).length);
  const flagged=outsideOf(rows);
  const assemblies=new Set(rows.map(row=>text(row.Assembly))).size;
  subtitle.textContent=`${assemblies} assembl${assemblies===1?'y':'ies'} × ${byMarker.size} genes · ${flagged.length} gene lengths outside the RefSeq range widened by ${d3.format('~g')(tolerance)}%, or absent · ${new Set(flagged.map(row=>text(row.Marker))).size} genes affected.`;
  legend.innerHTML=`<span><svg width="12" height="12"><path transform="translate(6,6)" d="${d3.symbol(d3.symbolDiamond,54)()}" fill="#475569"/></svg>RefSeq genome</span><span><i style="background:rgba(2,158,115,.18)"></i>reference range ± ${d3.format('~g')(tolerance)}%</span><span><i style="background:#029E73;border-radius:50%"></i>assembly inside</span><span><i style="background:#DE8F05;border-radius:50%"></i>assembly outside</span><span><i style="background:#fff;border:2px solid #0f172a;border-radius:50%"></i>recommended</span><span>0% = median length of the gene in the RefSeq genomes</span>`;
  const limit=Math.max(15,tolerance*2.5);
  const items=[];
  let previousClass=null;
  markers.forEach(marker=>{
    const markerRows=byMarker.get(marker);
    const category=markerCategory(marker);
    if(category!==previousClass){items.push({header:category==='Other'?'Other genes':category});previousClass=category;}
    const median=num(markerRows[0]['Reference median']);
    const low=num(markerRows[0]['Reference min']), high=num(markerRows[0]['Reference max']);
    const projects=[...new Set(markerRows.map(row=>text(row['Project name'])))];
    // Diamonds: each RefSeq genome of the projects in view, relative to the median of its project.
    const refs=[], seen=new Set(), bands=[];
    projects.forEach(project=>{
      const first=markerRows.find(row=>text(row['Project name'])===project);
      const projectMedian=num(first['Reference median']);
      if(!projectMedian)return;
      const pct=value=>100*(value-projectMedian)/projectMedian;
      bands.push([pct(num(first['Reference min'])*(1-tolerance/100)),pct(num(first['Reference max'])*(1+tolerance/100))]);
      (accessions.get(project)||[]).forEach(accession=>{
        const ref=lengths.get(accession); const value=ref?ref.genes.get(marker):null;
        if(value===null||value===undefined||seen.has(accession))return;
        seen.add(accession);
        refs.push({value:pct(value),tip:`<b><i>${esc(ref.organism)}</i></b> · ${esc(accession)} (RefSeq)<br>${esc(marker)}: ${d3.format(',')(value)} bp (${d3.format('+.1f')(pct(value))}% from the median)`});
      });
    });
    const uniqueBands=[...new Map(bands.map(band=>[band.map(v=>v.toFixed(3)).join(','),band])).values()];
    const absent=markerRows.filter(row=>text(row.Status)==='Absent');
    const points=markerRows.filter(row=>text(row.Status)!=='Absent').map((row,i)=>{
      const deviation=num(row['Deviation from median (%)']);
      const status=text(row.Status);
      const pick=recommended.has(text(row.Assembly));
      return {value:deviation,pick:referenceGenesScope==='all'&&pick,jitter:i,color:status==='Within'?'#029E73':'#DE8F05',
        tip:`<b>${esc(marker)}</b> · ${esc(projectDisplayText(projectRecord(row['Project name'])))} · ${runLabel(row)}${pick?' (recommended)':''}<br>${d3.format(',')(num(row.Length,0))} bp, ${deviation===null?'—':d3.format('+.1f')(deviation)+'%'} from the RefSeq median (${d3.format(',')(num(row['Reference median'],0))} bp)<br>RefSeq ${d3.format(',')(num(row['Reference min'],0))}–${d3.format(',')(num(row['Reference max'],0))} bp in ${esc(row['References with the gene'])} genome(s) · ${esc(status)}`};
    });
    const outside=outsideOf(markerRows).length;
    const range=low===high?`${d3.format(',')(low)} bp`:`${d3.format(',')(low)}–${d3.format(',')(high)} bp`;
    items.push({
      label:selection=>selection.attr('font-weight',outside?750:500).attr('fill',outside?'#9a3412':'#0f172a').text(marker),
      refs, bands:uniqueBands, points,
      right:`RefSeq ${range}${outside?` · ${outside} outside`:''}`, rightColor:outside?'#9a3412':'#64748b',
      absent:absent.length&&!points.length?`absent from ${absent.length} assembl${absent.length===1?'y':'ies'}`:null,
      absentTip:absent.length?`Absent from: ${absent.map(row=>esc(`${projectDisplayText(projectRecord(row['Project name']))} · ${text(row['Seed Input'])} · k${text(row['K-mer'])} · _${text(row['Assembly copy'])}`)).join('<br>')}`:null,
    });
    if(absent.length&&points.length)items[items.length-1].right+=` · absent in ${absent.length}`;
  });
  if(!markers.length){emptyChart('referenceGenes','Every gene in view is inside the RefSeq range.');return;}
  drawStripChart('referenceGenes',{rows:items,domain:[-limit,limit],zero:0,labelWidth:110,rightWidth:230,rowHeight:26,axisTop:true,
    tickFormat:value=>`${value>0?'+':''}${d3.format('~g')(value)}%`,axisLabel:'Difference from the median length of the gene in the RefSeq genomes'});
}

// ------------------------------------------- composition against RefSeq (strip)
const COMPOSITION_METRICS=[
  ['GC %','GC % (genome)','.2f'],['AT skew','AT skew (genome)','.3f'],['GC skew','GC skew (genome)','.3f'],
  ['PCG GC %','GC % of the protein-coding genes','.2f'],['PCG + AT skew','AT skew, PCGs on the + strand','.3f'],['PCG + GC skew','GC skew, PCGs on the + strand','.3f'],
  ['PCG - AT skew','AT skew, PCGs on the − strand','.3f'],['PCG - GC skew','GC skew, PCGs on the − strand','.3f'],
];
let compositionMetric='GC %';
let compositionScope='recommended';
function renderCompositionStrip() {
  const card=document.getElementById('compositionStripCard');
  const recommendedSet=recommendedAssemblies();
  const rows=organpipeRows('composition').filter(row=>compositionScope==='all'||recommendedSet.has(text(row.Assembly)));
  const accessions=referenceAccessionsByProject();
  const hasReferences=rows.some(row=>(accessions.get(text(row['Project name']))||[]).some(accession=>referenceCompositionByAccession.has(accession)));
  card.style.display=(ORGANPIPE.reference_composition||[]).length?'':'none';
  if(!(ORGANPIPE.reference_composition||[]).length)return;
  const [column,label,format]=COMPOSITION_METRICS.find(item=>item[0]===compositionMetric)||COMPOSITION_METRICS[0];
  const recommended=recommendedAssemblies();
  const projects=[...new Set(rows.map(row=>text(row['Project name'])))].sort((a,b)=>a.localeCompare(b,undefined,{numeric:true}));
  const items=[], values=[];
  let outside=0, singleReference=0;
  projects.forEach(project=>{
    const assemblies=rows.filter(row=>text(row['Project name'])===project);
    const refs=(accessions.get(project)||[]).map(accession=>referenceCompositionByAccession.get(accession)).filter(Boolean);
    const refValues=refs.map(ref=>num(ref[column])).filter(value=>value!==null);
    // A range needs two references; with one, the chart shows the distance to it without a verdict.
    const [low,high]=refValues.length>1?d3.extent(refValues):[null,null];
    const median=refValues.length?d3.median(refValues):null;
    if(refValues.length===1)singleReference+=1;
    const points=assemblies.map((row,i)=>{
      const value=num(row[column]); if(value!==null)values.push(value);
      const pick=recommended.has(text(row.Assembly));
      const inside=low===null||value===null||(value>=low&&value<=high);
      if(!inside)outside+=1;
      return {value,pick,jitter:i,color:low===null?'#0173B2':(inside?'#029E73':'#DE8F05'),
        tip:`<b>${esc(projectDisplayText(projectRecord(project)))}</b> · ${runLabel(row)}${pick?' (recommended)':''}<br>${esc(label)}: ${fmtNum(value,format)}${median===null?'':`<br>RefSeq ${low===null?fmtNum(median,format)+' (one genome)':`${fmtNum(low,format)} to ${fmtNum(high,format)} (median ${fmtNum(median,format)})`}; difference ${d3.format('+'+format)(value-median)}`}`};
    });
    refValues.forEach(value=>values.push(value));
    items.push({
      label:selection=>setSvgProjectLabel(selection,projectRecord(project),{suffix:refs.length?` · ${refs.length} RefSeq`:' · no RefSeq'}),
      bands:low===null?[]:[[low,high]],
      refs:refs.map(ref=>({value:num(ref[column]),tip:`<b><i>${esc(ref.Organism)}</i></b> · ${esc(ref.Accession)} (RefSeq)<br>${esc(label)}: ${fmtNum(ref[column],format)}`})),
      points,
    });
  });
  document.getElementById('compositionStripSubtitle').textContent=hasReferences
    ? `${rows.length} assembl${rows.length===1?'y':'ies'} of ${projects.length} sample(s) · ${singleReference===projects.length?`one RefSeq genome per sample, so no range: read the distance between the circles and the diamond (tooltips give the difference)`:`${outside} outside the range of the RefSeq genomes of their sample for ${label}`}.`
    : 'No RefSeq genome matches the samples in view.';
  if(!values.length){emptyChart('compositionStrip','No composition value for the current filters.');return;}
  let [low,high]=d3.extent(values);
  const pad=Math.max(column.includes('skew')?.01:.5,(high-low)*.08);
  drawStripChart('compositionStrip',{rows:items,domain:d3.scaleLinear().domain([low-pad,high+pad]).nice().domain(),labelWidth:Math.min(380,Math.max(240,svgLabelWidth(projects.map(project=>projectDisplayText(projectRecord(project))+' · 9 RefSeq'),10.5)+24)),
    rowHeight:38,axisLabel:label,tickFormat:d3.format(column.includes('skew')?'.2f':'.1f'),zero:column.includes('skew')?0:undefined});
}

// --------------------------------------------- marker comparison (diverging)
let markerValueMode='length';
let markerOnlyDifferent=false;
function markerModes(rows) {
  const modes=new Map();
  d3.groups(rows,row=>text(row.Marker)).forEach(([marker,items])=>{
    const counts=d3.rollup(items,v=>v.length,row=>num(row['Marker length']));
    modes.set(marker,[...counts].sort((a,b)=>b[1]-a[1]||a[0]-b[0])[0][0]);
  });
  return modes;
}

function renderMarkerHeatmap() {
  const legend=document.getElementById('markerLegend');
  const all=REPORT.markers.filter(matches).filter(row=>num(row['Marker length'])!==null);
  const rows=all.filter(row=>markerCategorySelection==='All'||markerCategory(row.Marker)===markerCategorySelection);
  if(!rows.length){legend.innerHTML='';document.getElementById('markerSubtitle').textContent='';return emptyChart('markerLengthHeatmap',`No ${markerCategorySelection} marker-length data for the selected filters.`);}
  clearChart('markerLengthHeatmap');
  const expected=(ORGANPIPE.expected_markers||[]).map(text);
  const markers=unique(rows,'Marker').map(text).sort((a,b)=>{const ca=GENE_CLASS_ORDER.indexOf(markerCategory(a)), cb=GENE_CLASS_ORDER.indexOf(markerCategory(b));const ia=expected.indexOf(a), ib=expected.indexOf(b);return ca-cb||(ia<0?999:ia)-(ib<0?999:ib)||a.localeCompare(b,undefined,{numeric:true});});
  const copyKey=row=>`${rowKey(row)}\0${text(row['Assembly copy'])}`;
  const assemblies=new Map();
  rows.forEach(row=>{
    const key=copyKey(row);
    if(!assemblies.has(key))assemblies.set(key,{key,row,values:new Map()});
    assemblies.get(key).values.set(text(row.Marker),num(row['Marker length']));
  });
  const accessions=referenceAccessionsByProject();
  const refLengths=referenceGeneLengths();
  const projects=d3.groups([...assemblies.values()],item=>text(item.row['Project name'])).sort((a,b)=>projectDisplayText(a[1][0].row).localeCompare(projectDisplayText(b[1][0].row),undefined,{numeric:true}));
  const lines=[];
  const recommendedNames=recommendedAssemblies();
  let differing=0, total=0;
  projects.forEach(([project,items])=>{
    const projectRows=rows.filter(row=>text(row['Project name'])===project);
    const modes=markerModes(projectRows);
    items.sort((a,b)=>text(a.row['Seed Input']).localeCompare(text(b.row['Seed Input']),undefined,{numeric:true})||num(a.row['K-mer'],0)-num(b.row['K-mer'],0)||num(a.row['Assembly copy'],0)-num(b.row['Assembly copy'],0));
    const differs=item=>markers.some(marker=>modes.has(marker)&&item.values.get(marker)!==modes.get(marker));
    total+=items.length;
    const shown=items.filter(item=>{const d=differs(item);if(d)differing+=1;return !markerOnlyDifferent||d;});
    lines.push({type:'mode',project,modes,count:items.length,shown:shown.length,row:items[0].row});
    const refs=(accessions.get(project)||[]).map(accession=>refLengths.get(accession)).filter(Boolean);
    if(refs.length){
      const medians=new Map(markers.map(marker=>{const values=refs.map(ref=>ref.genes.get(marker)).filter(value=>value!==undefined&&value!==null);return [marker,values.length?d3.median(values):null];}));
      lines.push({type:'ref',project,medians,refs:refs.length,modes});
    }
    shown.forEach(item=>lines.push({type:'assembly',project,item,modes}));
  });
  document.getElementById('markerSubtitle').textContent=`${total} assembly copies of ${projects.length} sample(s) × ${markers.length} ${markerCategorySelection==='All'?'markers':markerCategorySelection} · ${differing} with at least one marker length different from the mode of their sample.`;
  const limit=d3.max(lines.filter(line=>line.type==='assembly'),line=>d3.max(markers,marker=>{const value=line.item.values.get(marker), mode=line.modes.get(marker);return value===undefined||mode===undefined?0:Math.abs(value-mode);}))||1;
  const scaleMax=Math.max(3,Math.min(60,limit));
  const color=value=>{ if(value===0)return '#ffffff'; const t=Math.min(1,Math.sqrt(Math.abs(value)/scaleMax)); return value<0?d3.interpolateRgb('#e6f1f8','#0173B2')(t):d3.interpolateRgb('#fcefd9','#DE8F05')(t); };
  legend.innerHTML=`<span><i style="background:#0173B2"></i>shorter than the mode</span><span><i style="background:#9ccbe6"></i>1–2 bp shorter</span><span><i style="background:#fff;border:1px solid #cbd5e1"></i>same length as the mode</span><span><i style="background:#f3c98b"></i>1–2 bp longer</span><span><i style="background:#DE8F05"></i>longer (full colour at ±${d3.format('~g')(scaleMax)} bp)</span><span><i class="hatch-swatch"></i>not annotated</span><span><b>Bold row</b>: mode of the sample · <b>RefSeq</b>: median of the reference genomes</span>`;
  const container=document.getElementById('markerLengthHeatmap');
  const labelWidth=Math.min(400,Math.max(250,svgLabelWidth(projects.map(([,items])=>projectDisplayText(items[0].row)+' · Mode (99 of 99 differ)'),10.5)+30));
  const available=(container.clientWidth||1100)-labelWidth-12;
  const cellWidth=Math.max(markerCategorySelection==='tRNAs'||markers.length>24?34:44,Math.min(72,available/markers.length));
  const rotate=markers.some(marker=>marker.length*6.2>cellWidth-4);
  const top=rotate?Math.min(96,18+d3.max(markers,marker=>marker.length)*5.4):26;
  const rowHeight=22, gap=12;
  let cursor=top;
  const layout=lines.map((line,index)=>{ if(line.type==='mode'&&index)cursor+=gap; const y=cursor; cursor+=rowHeight; return {line,y}; });
  const height=cursor+8, width=Math.max(container.clientWidth||900,labelWidth+markers.length*cellWidth+12);
  const svg=d3.select('#markerLengthHeatmap').append('svg').attr('width',width).attr('height',height).attr('viewBox',`0 0 ${width} ${height}`);
  const defs=svg.append('defs');
  defs.append('pattern').attr('id','markerHatch').attr('patternUnits','userSpaceOnUse').attr('width',5).attr('height',5).html('<rect width="5" height="5" fill="#f1f5f9"/><path d="M0,5 l5,-5" stroke="#94a3b8" stroke-width="1"/>');
  markers.forEach((marker,j)=>{
    const cx=labelWidth+(j+.5)*cellWidth;
    const label=svg.append('text').attr('font-size',10).attr('font-weight',750).attr('fill','#0f172a').text(marker);
    if(rotate)label.attr('x',cx).attr('y',top-5).attr('transform',`rotate(-55,${cx},${top-5})`);
    else label.attr('x',cx).attr('y',top-8).attr('text-anchor','middle');
  });
  const cellText=(value,mode)=>markerValueMode==='difference'&&mode!==undefined?(value===mode?'0':d3.format('+')(value-mode)):d3.format(',')(value);
  layout.forEach(({line,y})=>{
    if(line.type==='mode'){
      svg.append('rect').attr('x',0).attr('y',y).attr('width',width).attr('height',rowHeight).attr('fill','#e8f3f9');
      const label=svg.append('text').attr('x',labelWidth-10).attr('y',y+15).attr('text-anchor','end').attr('font-size',10.5).attr('fill','#0f172a');
      setSvgProjectLabel(label,projectRecord(line.project),{suffix:markerOnlyDifferent?` · Mode (${line.shown} of ${line.count} differ)`:' · Mode'});
      label.on('mousemove',event=>hover(event,`<b>${esc(projectDisplayText(projectRecord(line.project)))}</b><br>Most common length of each marker among the ${line.count} assembly copies of the sample${markerOnlyDifferent?` (${line.shown} differ and are shown)`:''}.`)).on('mouseleave',unhover);
      markers.forEach((marker,j)=>{ const mode=line.modes.get(marker); if(mode===undefined)return; svg.append('text').attr('x',labelWidth+(j+.5)*cellWidth).attr('y',y+15).attr('text-anchor','middle').attr('font-size',10).attr('font-weight',800).attr('fill','#0f172a').text(d3.format(',')(mode)); });
      return;
    }
    if(line.type==='ref'){
      svg.append('text').attr('x',labelWidth-10).attr('y',y+15).attr('text-anchor','end').attr('font-size',10).attr('font-style','italic').attr('fill','#475569').text(`RefSeq median (${line.refs} genome${line.refs===1?'':'s'})`);
      markers.forEach((marker,j)=>{
        const median=line.medians.get(marker), mode=line.modes.get(marker);
        if(median===null||median===undefined)return;
        const differs=mode!==undefined&&Math.abs(median-mode)>0;
        svg.append('text').attr('x',labelWidth+(j+.5)*cellWidth).attr('y',y+15).attr('text-anchor','middle').attr('font-size',9.5).attr('font-style','italic').attr('font-weight',differs?750:400).attr('fill',differs?'#9a3412':'#64748b').text(markerValueMode==='difference'&&mode!==undefined?(median===mode?'0':d3.format('+')(median-mode)):d3.format(',')(median))
          .on('mousemove',event=>hover(event,`<b>${esc(marker)}</b> · RefSeq median ${d3.format(',')(median)} bp${mode!==undefined?`<br>Mode of the sample ${d3.format(',')(mode)} bp (${d3.format('+')(mode-median)} bp)`:''}`)).on('mouseleave',unhover);
      });
      return;
    }
    const {item,modes}=line;
    const label=svg.append('text').attr('x',labelWidth-10).attr('y',y+15).attr('text-anchor','end').attr('font-size',10).attr('fill','#334155');
    const file=text(item.row['GenBank file']);
    const isPick=[...recommendedNames].some(name=>file===`${name}.rotated.gb`||file===`${name}.gb`);
    label.text(`${text(item.row['Seed Input'])} · k${text(item.row['K-mer'])} · _${text(item.row['Assembly copy'])}${isPick?' ★':''}`).attr('font-weight',isPick?750:400);
    markers.forEach((marker,j)=>{
      const value=item.values.get(marker), mode=modes.get(marker);
      const x0=labelWidth+j*cellWidth;
      if(value===undefined||value===null){
        svg.append('rect').attr('x',x0+1).attr('y',y+1).attr('width',cellWidth-2).attr('height',rowHeight-2).attr('rx',3).attr('fill','url(#markerHatch)')
          .on('mousemove',event=>hover(event,`<b>${esc(marker)}</b> · ${esc(projectDisplayText(item.row))} · ${esc(item.row['Seed Input'])} · k${esc(item.row['K-mer'])} · _${esc(item.row['Assembly copy'])}<br>Not annotated in this assembly`)).on('mouseleave',unhover);
        return;
      }
      const difference=mode===undefined?0:value-mode;
      svg.append('rect').attr('x',x0+1).attr('y',y+1).attr('width',cellWidth-2).attr('height',rowHeight-2).attr('rx',3).attr('fill',color(difference)).attr('stroke',difference?'none':'#e2e8f0')
        .on('mousemove',event=>hover(event,`<b>${esc(marker)}</b> · ${esc(projectDisplayText(item.row))}<br>${esc(item.row['Seed Input'])} · k${esc(item.row['K-mer'])} · _${esc(item.row['Assembly copy'])}${isPick?' (recommended)':''}<br>${d3.format(',')(value)} bp · mode of the sample ${d3.format(',')(mode)} bp${difference?` (${d3.format('+')(difference)} bp)`:''}`)).on('mouseleave',unhover);
      const strong=Math.abs(difference)>=scaleMax*.35;
      svg.append('text').attr('x',x0+cellWidth/2).attr('y',y+15).attr('text-anchor','middle').attr('font-size',9.5).attr('font-weight',difference?750:400).attr('fill',strong?'#ffffff':(difference?'#0f172a':'#94a3b8')).attr('pointer-events','none').text(cellText(value,mode));
    });
  });
}

// -------------------------------------------------- RSCU with RefSeq genomes
function referenceRscuItems() {
  const accessions=referenceAccessionsByProject();
  const projects=new Set(organpipeRows('composition').map(row=>text(row['Project name'])));
  const wanted=new Set([...projects].flatMap(project=>accessions.get(project)||[]));
  return [...wanted].map(accession=>referenceRscuByAccession.get(accession)).filter(Boolean).map(ref=>({...ref,isReference:true,Assembly:`ref:${text(ref.Accession)}`}));
}

function initCompositionControls() {
  document.getElementById('compositionMetric').innerHTML=COMPOSITION_METRICS.map(([column,label])=>`<option value="${esc(column)}" ${column===compositionMetric?'selected':''}>${esc(label)}</option>`).join('');
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
  renderOrganpipeSections();
  renderSamplingMap();
  renderMarkerHeatmap();
  renderRepeatTable();
  renderSnpMatrices();
  enableTableDragScroll();
}

async function start() {
  try {
    await loadD3();
    await Promise.all([loadMapLibre(),loadTippy()]);
    abbreviateSpecies=false;
    document.getElementById('abbreviateSpecies').checked=false;
    renderTabs();
    resetFilterSelections();
    initChartGuides();
    initCompositionControls();
    renderAll();
    initStaticTooltips();
    initStickyFilterLogo();
    initProjectPicker();
    initMarkerCategoryControls();
    initSamplingMapControls();
    initRecommendedPaths();
    enableTableDragScroll();
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
document.getElementById('snpIncludeIncomplete').addEventListener('change',event=>{ snpIncludeIncomplete=event.target.checked; renderSnpMatrices(); });
document.getElementById('qualitySearch').addEventListener('input',renderQualityTable);
document.getElementById('integritySearch').addEventListener('input',renderIntegrityTable);
document.getElementById('integrityShowInfo').addEventListener('change',renderIntegrityTable);
document.getElementById('rscuSelect').addEventListener('change',event=>{ rscuSelection=event.target.value; renderRscu(); });
document.getElementById('rscuView').addEventListener('change',event=>{ rscuView=event.target.value; renderRscu(); });
document.getElementById('pilonShowValues').addEventListener('change',event=>{ pilonShowValues=event.target.checked; renderPilonMetrics(); });
document.getElementById('qualityOnlyAlerts').addEventListener('change',renderQualityTable);
document.getElementById('repeatSearch').addEventListener('input',renderRepeatTable);
document.getElementById('heteroplasmySearch').addEventListener('input',renderHeteroplasmy);
document.getElementById('heteroplasmyShowLow').addEventListener('change',renderHeteroplasmy);
document.getElementById('referenceMetric').addEventListener('change',event=>{ referenceMetric=event.target.value; renderReferenceStrip(); });
document.getElementById('referenceGenesScope').addEventListener('change',event=>{ referenceGenesScope=event.target.value; renderReferenceGenes(); });
document.getElementById('referenceGenesOutside').addEventListener('change',event=>{ referenceGenesOnlyOutside=event.target.checked; renderReferenceGenes(); });
document.getElementById('compositionMetric').addEventListener('change',event=>{ compositionMetric=event.target.value; renderCompositionStrip(); });
document.getElementById('compositionScope').addEventListener('change',event=>{ compositionScope=event.target.value; renderCompositionStrip(); });
document.getElementById('markerValueMode').addEventListener('change',event=>{ markerValueMode=event.target.value; renderMarkerHeatmap(); });
document.getElementById('markerOnlyDifferent').addEventListener('change',event=>{ markerOnlyDifferent=event.target.checked; renderMarkerHeatmap(); });

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
        output_dir=output_dir,
        organpipe_results=kwargs.get("organpipe_results"),
    )

    report_config = {
        "max_repeat_families": int(config.get("max_repeat_families", 18)),
        "snp_columns_per_panel": int(config.get("snp_columns_per_panel", 60)),
        "snp_project_gap": int(config.get("snp_project_gap", 12)),
        "snp_compact_max_columns": int(config.get("snp_compact_max_columns", 14)),
        "snp_min_length_ratio": float(config.get("snp_min_length_ratio", 0.9)),
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
