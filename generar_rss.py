#!/usr/bin/env python3
"""Genera un RSS con los eventos de https://www.turismoasturias.es/agenda-de-asturias

Recorre la portada de la agenda y cada categoría (con su paginación),
quita duplicados y escribe agenda-asturias.xml.
"""
import re
import sys
import time
from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import quote, urlparse
from xml.sax.saxutils import escape

import requests
from bs4 import BeautifulSoup

BASE = "https://www.turismoasturias.es"
SECCIONES = [
    "", "/fiestas", "/gastronomia", "/museos", "/cine-y-espectaculos", "/deporte",
    "/ocio-infantil", "/rutas-y-visitas-guiadas", "/ferias-mercados",
]
PORTLET = "as_asac_calendar_suite_CalendarSuitePortlet_INSTANCE_JXvXAPSD7JC0"
PAGINA_AGENDA = "117"  # p_l_id de la página de la agenda en la web
MAX_PAGINAS = 15
SALIDA = "agenda-asturias.xml"
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

sesion = requests.Session()
sesion.headers["User-Agent"] = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36")


def descargar(url):
    for intento in range(3):
        try:
            r = sesion.get(url, timeout=30)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            print(f"  aviso: {url} -> {e}", file=sys.stderr)
            time.sleep(3 * (intento + 1))
    return ""


def fecha(texto):
    try:
        return datetime.strptime(texto[:19], "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def fecha_legible(d):
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}" if d else ""


def parsear(html, categoria):
    soup = BeautifulSoup(html, "html.parser")
    eventos = []
    for card in soup.select('[itemtype="http://schema.org/Event"]'):
        enlace = card.select_one('a[itemprop="url"][href*="/calendarsuite/event/"]')
        nombre = card.select_one('[itemprop="name"]')
        if not enlace or not nombre:
            continue
        url = enlace["href"].split("?")[0]
        if url.startswith("/"):
            url = BASE + url
        m = re.search(r"/calendarsuite/event/[^/]+/(\d+)", url)
        if not m:
            continue
        inicio = card.select_one('[itemprop="startDate"]')
        fin = card.select_one('[itemprop="endDate"]')
        lugar = card.select_one('[itemprop="address"]')
        resumen = card.select_one(".card-hover")
        hora = card.select_one(".hour")
        imagen = None
        estilo = card.select_one(".image-wrapper")
        if estilo and estilo.get("style"):
            mi = re.search(r"url\(['\"]?([^'\")]+)", estilo["style"])
            if mi:
                imagen = mi.group(1)
                if imagen.startswith("/"):
                    imagen = BASE + imagen
        eventos.append({
            "id": m.group(1),
            "titulo": nombre.get_text(strip=True),
            "url": url,
            "lugar": lugar.get_text(strip=True) if lugar else "",
            "inicio": fecha(inicio.get("date") if inicio else None),
            "fin": fecha(fin.get("date") if fin else None),
            "hora": hora.get_text(" ", strip=True) if hora else "",
            "resumen": resumen.get_text(" ", strip=True) if resumen else "",
            "imagen": imagen,
            "categorias": {categoria} if categoria else set(),
        })
    return eventos


def recoger():
    todos = {}
    for seccion in SECCIONES:
        categoria = seccion.strip("/").replace("-", " ").capitalize()
        vistos_seccion = set()
        for pagina in range(1, MAX_PAGINAS + 1):
            url = (f"{BASE}/agenda-de-asturias{seccion}?p_p_id={PORTLET}&p_p_lifecycle=0"
                   f"&_{PORTLET}_cur={pagina}")
            eventos = parsear(descargar(url), categoria)
            nuevos = [e for e in eventos if e["id"] not in vistos_seccion]
            if not nuevos:
                break  # página vacía o repetida: fin de la paginación
            for e in nuevos:
                vistos_seccion.add(e["id"])
                if e["id"] in todos:
                    todos[e["id"]]["categorias"] |= e["categorias"]
                else:
                    todos[e["id"]] = e
            time.sleep(1)
        print(f"{seccion or '/'}: {len(vistos_seccion)} eventos")
    return list(todos.values())


def fechas_anteriores():
    """Fecha en que se vio cada evento por primera vez (sale del feed anterior)."""
    try:
        texto = open(SALIDA, encoding="utf-8").read()
    except OSError:
        return {}
    return dict(re.findall(r'<guid isPermaLink="false">([^<]+)</guid><pubDate>([^<]+)</pubDate>', texto))


def enlace_es(url):
    """Enlace que abre el evento siempre en español.

    La web recuerda el idioma del visitante en una cookie (el visor de News
    Explorer puede quedarse en alemán); update_language la fija a es_ES.
    """
    ruta = urlparse(url).path
    return (f"{BASE}/c/portal/update_language?p_l_id={PAGINA_AGENDA}"
            f"&redirect={quote(ruta, safe='')}&languageId=es_ES")


def rss(eventos):
    ahora = datetime.now(timezone.utc)
    vistos = fechas_anteriores()
    items = []
    for e in sorted(eventos, key=lambda x: x["inicio"] or datetime.max):
        fechas = fecha_legible(e["inicio"])
        if e["fin"] and e["inicio"] and e["fin"].date() != e["inicio"].date():
            fechas += f" – {fecha_legible(e['fin'])}"
        cabecera = " · ".join(x for x in [fechas, e["hora"], e["lugar"]] if x)
        html = ""
        if e["imagen"]:
            html += f'<p><img src="{escape(e["imagen"])}" alt=""/></p>'
        html += f"<p><strong>{escape(cabecera)}</strong></p>"
        if e["resumen"]:
            html += f"<p>{escape(e['resumen'])}</p>"
        titulo = e["titulo"] + (f" ({e['lugar']})" if e["lugar"] and e["lugar"] not in e["titulo"] else "")
        guid = f"turismoasturias-{e['id']}"
        pub = vistos.get(guid) or format_datetime(ahora)  # fecha de alta en el feed
        cats = "".join(f"<category>{escape(c)}</category>" for c in sorted(e["categorias"]))
        items.append(
            "<item>"
            f"<title>{escape(titulo)}</title>"
            f"<link>{escape(enlace_es(e['url']))}</link>"
            f'<guid isPermaLink="false">{guid}</guid>'
            f"<pubDate>{pub}</pubDate>"
            f"{cats}"
            f"<description><![CDATA[{html}]]></description>"
            "</item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"><channel>'
        "<title>Agenda de Asturias · Turismo Asturias</title>"
        f"<link>{BASE}/agenda-de-asturias</link>"
        "<description>Eventos de la agenda oficial de Turismo Asturias</description>"
        "<language>es-ES</language>"
        f"<lastBuildDate>{format_datetime(ahora)}</lastBuildDate>"
        + "\n".join(items)
        + "</channel></rss>\n"
    )


if __name__ == "__main__":
    eventos = recoger()
    if not eventos:
        sys.exit("No se ha encontrado ningún evento: no se sobrescribe el feed.")
    with open(SALIDA, "w", encoding="utf-8") as f:
        f.write(rss(eventos))
    print(f"Total: {len(eventos)} eventos -> {SALIDA}")
