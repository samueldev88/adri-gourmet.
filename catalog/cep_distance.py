import json
import math
import re
import urllib.error
import urllib.request


class CepNotFound(Exception):
    """CEP não existe."""


class LookupUnavailable(Exception):
    """Serviço de consulta fora do ar ou sem coordenadas."""


def normalize_cep(value):
    """Retorna só os 8 dígitos do CEP, ou None se for inválido."""
    digits = re.sub(r"\D", "", value or "")
    return digits if len(digits) == 8 else None


def haversine_km(lat1, lon1, lat2, lon2):
    """Distância em km em linha reta entre dois pontos."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _get_json(url, timeout=6):
    req = urllib.request.Request(url, headers={"User-Agent": "adriegourmet/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _awesomeapi(cep):
    data = _get_json(f"https://cep.awesomeapi.com.br/json/{cep}")
    lat, lon = data.get("lat"), data.get("lng")
    if not lat or not lon:
        raise LookupUnavailable("Sem coordenadas")
    address = ", ".join(
        p for p in (data.get("address"), data.get("district"), data.get("city")) if p
    )
    return {"lat": float(lat), "lon": float(lon), "address": address}


def _brasilapi(cep):
    data = _get_json(f"https://brasilapi.com.br/api/cep/v2/{cep}")
    coords = (data.get("location") or {}).get("coordinates") or {}
    lat, lon = coords.get("latitude"), coords.get("longitude")
    if not lat or not lon:
        raise LookupUnavailable("Sem coordenadas")
    address = ", ".join(
        p for p in (data.get("street"), data.get("neighborhood"), data.get("city")) if p
    )
    return {"lat": float(lat), "lon": float(lon), "address": address}


def lookup_cep(cep):
    """Devolve {'lat', 'lon', 'address'} para um CEP de 8 dígitos."""
    not_found = 0
    for provider in (_awesomeapi, _brasilapi):
        try:
            return provider(cep)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                not_found += 1
        except (urllib.error.URLError, TimeoutError, ValueError, LookupUnavailable):
            pass
    if not_found == 2:
        raise CepNotFound(cep)
    raise LookupUnavailable(cep)