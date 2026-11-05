"""
Dynamic Software Catalog & Autonomous Package Installer for OmniNet.
Allows the AI assistant to recommend the best programs for any user need,
and automatically install them silently or open their official verified page.
"""

from __future__ import annotations
import subprocess
import webbrowser
import platform
import time
from typing import Dict, List, Optional, Any


SOFTWARE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "vlc": {
        "id": "vlc",
        "name": "VLC Media Player",
        "winget_id": "VideoLAN.VLC",
        "official_url": "https://www.videolan.org/",
        "category": "Multimedia y Videos",
        "modality": "Gratis (Código Abierto)",
        "description": "El reproductor de audio y video más completo del mundo; reproduce cualquier formato sin instalar codecs ni anuncios.",
        "keywords": ["video", "musica", "música", "reproducir", "reproductor", "película", "pelicula", "mp4", "mkv", "audio", "vlc", "ver videos"]
    },
    "7zip": {
        "id": "7zip",
        "name": "7-Zip",
        "winget_id": "7zip.7zip",
        "official_url": "https://www.7-zip.org/",
        "category": "Compresión y Archivos",
        "modality": "Gratis (Código Abierto)",
        "description": "Descompresor ultrarrápido y liviano para abrir archivos ZIP, RAR y 7Z sin límites ni cobros.",
        "keywords": ["descomprimir", "comprimir", "zip", "rar", "7z", "archivos comprimidos", "extraer", "7zip", "descompresor", "winrar"]
    },
    "libreoffice": {
        "id": "libreoffice",
        "name": "LibreOffice",
        "winget_id": "TheDocumentFoundation.LibreOffice",
        "official_url": "https://www.libreoffice.org/",
        "category": "Ofimática y Documentos",
        "modality": "Gratis (Código Abierto)",
        "description": "Suite ofimática completa con procesador de textos (Writer), planillas de cálculo (Calc) y presentaciones (Impress). Reemplazo libre de Word y Excel.",
        "keywords": ["word", "excel", "powerpoint", "documentos", "oficina", "ofimática", "ofimatica", "planillas", "presentaciones", "libreoffice", "escribir cartas"]
    },
    "firefox": {
        "id": "firefox",
        "name": "Mozilla Firefox",
        "winget_id": "Mozilla.Firefox",
        "official_url": "https://www.mozilla.org/firefox/",
        "category": "Navegación Web y Privacidad",
        "modality": "Gratis (Código Abierto)",
        "description": "Navegador web independiente, rápido y respetuoso con la privacidad que bloquea rastreadores y anuncios intrusivos.",
        "keywords": ["navegador", "internet", "navegar", "browser", "chrome", "edge", "privacidad", "firefox", "páginas web"]
    },
    "gimp": {
        "id": "gimp",
        "name": "GIMP",
        "winget_id": "GIMP.GIMP",
        "official_url": "https://www.gimp.org/",
        "category": "Diseño y Edición de Imágenes",
        "modality": "Gratis (Código Abierto)",
        "description": "Potente programa de edición fotográfica, dibujo y retoque de imágenes. Alternativa profesional gratuita a Photoshop.",
        "keywords": ["foto", "fotos", "fotografía", "editar fotos", "photoshop", "diseño", "dibujo", "imagenes", "imágenes", "gimp", "recortar fotos"]
    },
    "obs": {
        "id": "obs",
        "name": "OBS Studio",
        "winget_id": "OBSProject.OBSStudio",
        "official_url": "https://obsproject.com/",
        "category": "Grabación y Transmisión",
        "modality": "Gratis (Código Abierto)",
        "description": "La herramienta estándar de la industria para grabar la pantalla de tu PC o hacer transmisiones en directo en YouTube y Twitch sin marcas de agua.",
        "keywords": ["grabar", "pantalla", "grabar pantalla", "stream", "streaming", "twitch", "youtube", "obs", "grabar juegos", "clases virtuales"]
    },
    "keepassxc": {
        "id": "keepassxc",
        "name": "KeePassXC",
        "winget_id": "KeePassXCTeam.KeePassXC",
        "official_url": "https://keepassxc.org/",
        "category": "Seguridad y Contraseñas",
        "modality": "Gratis (Código Abierto)",
        "description": "Bóveda cifrada militar que almacena todas tus contraseñas en tu propio computador de forma segura sin depender de servidores ajenos.",
        "keywords": ["contraseña", "contraseñas", "password", "claves", "gestor de contraseñas", "guardar claves", "keepass", "seguridad"]
    },
    "vscode": {
        "id": "vscode",
        "name": "Visual Studio Code",
        "winget_id": "Microsoft.VisualStudioCode",
        "official_url": "https://code.visualstudio.com/",
        "category": "Programación y Desarrollo",
        "modality": "Gratis",
        "description": "El editor de código más popular y versátil para crear programas, sitios web y scripts en Python, JavaScript y más.",
        "keywords": ["programar", "codigo", "código", "desarrollo", "python", "javascript", "editor", "vscode", "visual studio code"]
    },
    "handbrake": {
        "id": "handbrake",
        "name": "HandBrake",
        "winget_id": "HandBrake.HandBrake",
        "official_url": "https://handbrake.fr/",
        "category": "Conversión y Compresión de Video",
        "modality": "Gratis (Código Abierto)",
        "description": "Reduce drásticamente el peso de tus videos o conviértelos a MP4 para que puedas enviarlos o subirlos mucho más rápido.",
        "keywords": ["convertir video", "comprimir video", "reducir video", "formato de video", "mp4", "handbrake", "achicar video"]
    },
    "kdenlive": {
        "id": "kdenlive",
        "name": "Kdenlive",
        "winget_id": "KDE.Kdenlive",
        "official_url": "https://kdenlive.org/",
        "category": "Edición de Video",
        "modality": "Gratis (Código Abierto)",
        "description": "Editor de video avanzado no lineal para cortar tomas, agregar música, títulos y efectos visuales sin costo.",
        "keywords": ["editar video", "edicion de video", "cortar video", "premiere", "montaje", "kdenlive", "hacer videos", "reels", "tiktok"]
    },
    "steam": {
        "id": "steam",
        "name": "Steam",
        "winget_id": "Valve.Steam",
        "official_url": "https://store.steampowered.com/",
        "category": "Videojuegos y Entretenimiento",
        "modality": "Gratis",
        "description": "La mayor tienda y plataforma de videojuegos del mundo con miles de juegos gratuitos y ofertas para PC.",
        "keywords": ["juego", "juegos", "gamer", "gaming", "videojuegos", "steam", "tienda de juegos", "jugar"]
    },
    "bleachbit": {
        "id": "bleachbit",
        "name": "BleachBit",
        "winget_id": "BleachBit.BleachBit",
        "official_url": "https://www.bleachbit.org/",
        "category": "Limpieza y Espacio en Disco",
        "modality": "Gratis (Código Abierto)",
        "description": "Limpiador profundo de archivos basura, cachés de navegadores y registros antiguos para liberar espacio sin tocar tus datos personales.",
        "keywords": ["limpiar", "basura", "cache", "temporales", "ccleaner", "espacio", "bleachbit", "liberar disco"]
    },
    "joplin": {
        "id": "joplin",
        "name": "Joplin",
        "winget_id": "Joplin.Joplin",
        "official_url": "https://joplinapp.org/",
        "category": "Notas y Organización",
        "modality": "Gratis (Código Abierto)",
        "description": "Cuaderno digital seguro para apuntes, listas de tareas y notas de estudio sincronizadas entre tu PC y tu teléfono.",
        "keywords": ["notas", "apuntes", "organizador", "recordatorios", "evernote", "bloc de notas", "joplin", "estudiar"]
    },
    "malwarebytes": {
        "id": "malwarebytes",
        "name": "Malwarebytes",
        "winget_id": "Malwarebytes.Malwarebytes",
        "official_url": "https://www.malwarebytes.com/",
        "category": "Seguridad y Antivirus",
        "modality": "Mixto",
        "description": "El limpiador de virus y malware más efectivo para detectar y eliminar infecciones que otros antivirus no ven.",
        "keywords": ["malware", "virus", "antivirus", "limpiar virus", "infección", "desinfectar", "malwarebytes", "amenazas"]
    },
    "protonvpn": {
        "id": "protonvpn",
        "name": "Proton VPN",
        "winget_id": "Proton.ProtonVPN",
        "official_url": "https://protonvpn.com/",
        "category": "Privacidad y VPN",
        "modality": "Gratis / Mixto",
        "description": "La mejor VPN gratuita con datos ilimitados bajo estricta ley suiza de privacidad para navegar seguro en redes Wi-Fi públicas.",
        "keywords": ["vpn", "ip", "ocultar ip", "privacidad", "wifi pública", "proton", "protonvpn"]
    }
}


def find_matching_software(query: str) -> List[Dict[str, Any]]:
    """Matches user queries or needs against the curated 2026 software catalog."""
    q = query.lower().strip()
    matches = []

    # Direct ID match
    for pkg_id, info in SOFTWARE_REGISTRY.items():
        if pkg_id in q or info["name"].lower() in q:
            matches.append(info)

    if matches:
        return matches

    # Keyword and category matching
    scores: Dict[str, int] = {}
    for pkg_id, info in SOFTWARE_REGISTRY.items():
        score = 0
        for kw in info["keywords"]:
            if kw in q:
                score += 2
        if info["category"].lower() in q:
            score += 3
        if score > 0:
            scores[pkg_id] = score

    sorted_ids = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
    for pkg_id in sorted_ids[:3]:
        matches.append(SOFTWARE_REGISTRY[pkg_id])

    return matches


def install_software_package(package_id_or_name: str, execute: bool = True) -> Dict[str, Any]:
    """
    Installs a software package silently via winget, or opens its verified official download URL.
    Ensures zero UI freezes, zero black console popups, and safe execution.
    """
    pkg_key = package_id_or_name.lower().strip()
    target_info = None

    # Lookup by ID or name
    for k, v in SOFTWARE_REGISTRY.items():
        if k == pkg_key or v["name"].lower() == pkg_key or v.get("winget_id", "").lower() == pkg_key:
            target_info = v
            break

    if not target_info:
        # Match by partial search
        matches = find_matching_software(pkg_key)
        if matches:
            target_info = matches[0]

    if not target_info:
        return {
            "success": False,
            "installed": False,
            "program_name": package_id_or_name,
            "message": f"No encontré '{package_id_or_name}' en el catálogo de software verificado 2026."
        }

    pname = target_info["name"]
    wid = target_info.get("winget_id")
    url = target_info["official_url"]

    if not execute:
        return {
            "success": True,
            "installed": False,
            "simulated": True,
            "program_name": pname,
            "winget_id": wid,
            "official_url": url,
            "message": f"Listo para instalar {pname} de forma silenciosa y segura."
        }

    is_win = platform.system().lower() == "windows"
    if is_win and wid:
        try:
            # Silent installation via winget
            cmd = [
                "winget", "install", "--id", wid,
                "--silent", "--accept-package-agreements",
                "--accept-source-agreements", "--disable-interactivity"
            ]
            cflags = 0x08000000  # CREATE_NO_WINDOW
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=180,
                creationflags=cflags
            )
            # 0 = success, 2316632065 (-2147418111) = already installed
            if res.returncode == 0 or "correctamente" in res.stdout.lower() or "installed" in res.stdout.lower():
                return {
                    "success": True,
                    "installed": True,
                    "program_name": pname,
                    "official_url": url,
                    "message": f"¡{pname} quedó instalado con éxito en tu computador! Ya puedes abrirlo y usarlo."
                }
            elif "ya está instalado" in res.stdout.lower() or "already installed" in res.stdout.lower():
                return {
                    "success": True,
                    "installed": True,
                    "already_installed": True,
                    "program_name": pname,
                    "official_url": url,
                    "message": f"{pname} ya estaba instalado en tu computador y se encuentra listo para usar."
                }
        except Exception:
            pass

    # Graceful fallback: Open verified official download page
    try:
        webbrowser.open(url)
        return {
            "success": True,
            "installed": False,
            "browser_opened": True,
            "program_name": pname,
            "official_url": url,
            "message": f"Abrí la página oficial y segura de {pname} en tu navegador para que puedas descargarlo directamente: {url}"
        }
    except Exception as e:
        return {
            "success": False,
            "installed": False,
            "program_name": pname,
            "official_url": url,
            "message": f"Puedes descargar {pname} de forma segura desde su sitio web oficial: {url}"
        }
