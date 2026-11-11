"""
OmniNet AI Agent Pro - Universal Entrypoint
Standalone executable and multiplatform agent runner.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# AUTO-ELEVATION -- must run before any real work.
# Re-launches the process with admin/root if not already elevated.
# Skip with --no-elevate flag (e.g., for MCP stdio mode).
# ---------------------------------------------------------------------------
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__" or getattr(sys, "frozen", False):
    if "--elevate" in sys.argv:
        sys.argv.remove("--elevate")
        try:
            from netopt.elevation import ensure_elevated
            ensure_elevated()
        except Exception as _elev_err:
            print(f"[OmniNet] Advertencia: no se pudo elevar privilegios: {_elev_err}", flush=True)
    # Remove --no-elevate from argv so argparse doesn't see it
    while "--no-elevate" in sys.argv:
        sys.argv.remove("--no-elevate")
import json
import time
import secrets
import argparse
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
import threading
import webbrowser

# Seguridad API Local (OMNI-003, OMNI-009)
LOCAL_SESSION_TOKEN = secrets.token_hex(16)
MAX_PAYLOAD_SIZE = 1024 * 1024  # 1 MB límite estricto de petición HTTP

# Ensure package directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from netopt.models import HealthState
from netopt.hal import get_hal, detect_platform
from netopt.diagnostics import (
    run_full_diagnostics,
    benchmark_all_resolvers,
    inspect_active_sockets,
    discover_path_mtu,
    audit_arp_lan,
    inspect_wifi_and_nic,
    measure_bandwidth_speed
)
from netopt.optimizer import NetworkOptimizer
from netopt.repair import NetworkRepairEngine
from netopt.rollback import RollbackManager, SNAPSHOT_DIR
from netopt.persistence import NetworkDaemon
from netopt.cli import format_diagnostics
from netopt.auto_trigger import get_sentinel, IncidentReport
from netopt.autonomous_scheduler import get_task_scheduler
from netopt.device_maintenance import DeviceMaintenanceEngine
from netopt.licensing import get_license_manager
from netopt.llm_gateway import LLMGateway, load_llm_config, save_llm_config
from netopt.ecosystem_subagents import get_ecosystem_orchestrator
from dataclasses import asdict


VERSION = "2.9.6"


def get_dashboard_html() -> str:
    return """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>OmniNet — Cuidador Automático de tu Internet y tu PC</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    :root {
      --bg: #0b1120;
      --card: #131c31;
      --border: #1e293b;
      --text: #f8fafc;
      --muted: #94a3b8;
    }
    body { background-color: var(--bg); color: var(--text); font-family: ui-sans-serif, system-ui, -apple-system, sans-serif; }
    .card { background-color: var(--card); border: 1px solid var(--border); border-radius: 1rem; }
  </style>
</head>
<body class="p-4 md:p-8 max-w-4xl mx-auto space-y-6">

  <!-- Encabezado Simple y Claro -->
  <header class="flex flex-wrap items-center justify-between pb-5 border-b border-[var(--border)] gap-4">
    <div class="flex items-center gap-3.5">
      <div class="w-12 h-12 rounded-2xl bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-2xl">🌐</div>
      <div>
        <h1 class="text-xl md:text-2xl font-bold text-white">OmniNet — Cuidador de tu Internet y tu PC</h1>
        <p class="text-xs md:text-sm text-[var(--muted)]">Mantiene tu internet rápido y tu computador limpio automáticamente cada 10 minutos</p>
      </div>
    </div>
    <div class="flex flex-wrap items-center gap-2">
      <!-- Selector de Idioma Mundial (ES / EN / PT) -->
      <select id="langSelector" onchange="applyWorldLanguage(this.value)" class="bg-slate-900 border border-slate-700 rounded-xl px-2.5 py-2 text-xs text-slate-200 font-semibold">
        <option value="es">🇪🇸 Español</option>
        <option value="en">🇺🇸 English</option>
        <option value="pt">🇧🇷 Português</option>
      </select>

      <!-- Botón de Plan / Suscripción Mundial -->
      <button id="btnPlanBadge" onclick="toggleLicenseModal()" class="flex items-center gap-1.5 bg-indigo-950/90 hover:bg-indigo-900 px-3.5 py-2 rounded-xl border border-indigo-700/70 text-xs font-bold text-indigo-300 transition">
        <span>💎</span> <span id="planBadgeText">Mi Plan: PRO ACTIVO</span>
      </button>

      <button id="btnSentinelToggle" onclick="toggleSentinel()" class="flex items-center gap-2 bg-emerald-950/80 hover:bg-emerald-900 px-3.5 py-2 rounded-xl border border-emerald-700/60 text-xs font-semibold text-emerald-300 transition">
        <span id="sentinelDot" class="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
        <span id="sentinelText">Cuidado Automático: ACTIVO</span>
      </button>
      <button onclick="toggleSettingsModal()" class="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs" title="Opciones de Inteligencia Artificial">
        ⚙️
      </button>
    </div>
  </header>

  <!-- Panel de Suscripción y Activación de Licencia Mundial -->
  <div id="licenseDrawer" class="hidden card p-5 space-y-4 border-indigo-600/60">
    <div class="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-800">
      <div>
        <h3 class="text-sm md:text-base font-bold text-white flex items-center gap-2">
          <span>💎</span> Tu Plan y Licencia de OmniNet IA
        </h3>
        <p class="text-xs text-[var(--muted)]">ID de este computador: <strong id="deviceIdText" class="text-slate-300">PC-...</strong> | Estado: <strong id="planStatusDetail" class="text-emerald-400">Plan Personal Pro Activo</strong></p>
      </div>
      <button onclick="toggleLicenseModal()" class="text-xs text-slate-400 hover:text-white">✕ Cerrar</button>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
      <div class="p-3.5 rounded-xl bg-slate-900 border border-slate-800 space-y-1.5">
        <div class="font-bold text-slate-200">🌱 Plan Gratis ($0)</div>
        <div class="text-slate-400">• 5 preguntas de prueba al Asistente IA<br>• Medidor de velocidad y estado</div>
        <button onclick="activateLicenseKey('FREE')" class="mt-2 w-full py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold">Probar Vista Gratis</button>
      </div>

      <div class="p-3.5 rounded-xl bg-indigo-950/50 border border-indigo-600/70 space-y-1.5">
        <div class="font-bold text-indigo-300">🚀 Plan Personal Pro ($4.99/mes)</div>
        <div class="text-slate-300">• Cuidado automático cada 10 min 24/7<br>• BleachBit + SDIO + Chat IA Ilimitado (1 PC)</div>
        <a id="linkBuyPro" href="https://omninet.lemonsqueezy.com/checkout/buy/pro-plan" target="_blank" class="block text-center mt-2 w-full py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-bold">💳 Suscribirme ($4.99/mes)</a>
      </div>

      <div class="p-3.5 rounded-xl bg-emerald-950/40 border border-emerald-700/60 space-y-1.5">
        <div class="font-bold text-emerald-300">🏠 Plan Hogar / Pyme ($12.99/mes)</div>
        <div class="text-slate-300">• Todo lo del Plan Pro incluido<br>• Hasta en <strong>5 computadores</strong></div>
        <a id="linkBuyFam" href="https://omninet.lemonsqueezy.com/checkout/buy/family-plan" target="_blank" class="block text-center mt-2 w-full py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold">💳 Suscribir 5 PCs ($12.99)</a>
      </div>
    </div>

    <div class="flex flex-wrap items-center gap-2 pt-1">
      <input type="text" id="licenseKeyInput" placeholder="Pega tu código aquí (ej. OMNI-PRO-XXXX-XXXX-XXXX)..." class="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-white">
      <button onclick="activateLicenseFromInput()" class="px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold">🔑 Activar mi Código</button>
    </div>
  </div>

  <!-- Panel Opcional de IA (Oculto por defecto) -->
  <div id="settingsDrawer" class="hidden card p-4 space-y-3">
    <div class="text-xs font-bold text-slate-300">Conexión Opcional de Inteligencia Artificial</div>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
      <select id="cfgProvider" onchange="onProviderChange()" class="bg-slate-900 border border-slate-700 rounded-lg p-2 text-xs text-white">
        <option value="deepseek">DeepSeek</option>
        <option value="openai">OpenAI</option>
        <option value="ollama">Modo Local (Sin Internet)</option>
      </select>
      <input type="text" id="cfgModel" value="deepseek-chat" class="bg-slate-900 border border-slate-700 rounded-lg p-2 text-xs text-white" placeholder="Modelo">
      <input type="password" id="cfgApiKey" class="bg-slate-900 border border-slate-700 rounded-lg p-2 text-xs text-white" placeholder="Clave secreta (Opcional)">
    </div>
    <div class="flex justify-end gap-2">
      <button onclick="toggleSettingsModal()" class="px-3 py-1.5 text-xs text-slate-400 hover:text-white">Cerrar</button>
      <button onclick="saveLlmSettings()" class="px-4 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold">Guardar</button>
    </div>
  </div>

  <!-- 3 Tarjetas de Estado Fáciles de Entender -->
  <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
    <div class="card p-5 space-y-1">
      <div class="text-xs text-[var(--muted)] font-medium">🌐 Estado de tu Internet</div>
      <div id="healthMetric" class="text-2xl font-bold text-emerald-400">Excelente</div>
      <div id="gatewayMetric" class="text-xs text-[var(--muted)]">Conectado a tu router sin cortes</div>
    </div>

    <div class="card p-5 space-y-1">
      <div class="text-xs text-[var(--muted)] font-medium">⚡ Rapidez y Estabilidad</div>
      <div id="latencyMetric" class="text-2xl font-bold text-blue-400">Calculando...</div>
      <div id="stabilityDesc" class="text-xs text-[var(--muted)]">Ideal para videos, llamadas y juegos</div>
    </div>

    <div class="card p-5 space-y-1">
      <div class="text-xs text-[var(--muted)] font-medium">💻 Salud y Espacio de tu PC</div>
      <div id="devDiskFree" class="text-2xl font-bold text-indigo-400">Revisando...</div>
      <div id="devRamFree" class="text-xs text-[var(--muted)]">Memoria lista y sin programas trabados</div>
    </div>
  </div>

  <!-- 4 Botones Grandes de 1 Clic -->
  <div class="card p-5 space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="text-sm md:text-base font-bold text-white">✨ ¿Qué quieres hacer con 1 clic?</h2>
      <span class="text-xs text-[var(--muted)]">Todo se hace con copia de seguridad automática</span>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <button onclick="oneClickBoostInternet()" id="btnBoostNet" class="p-4 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-left transition flex items-center gap-3.5 shadow-sm">
        <span class="text-2xl">🚀</span>
        <div>
          <div class="font-bold text-sm md:text-base">Acelerar mi Internet</div>
          <div class="text-xs text-blue-100">Hace que las páginas, películas y videollamadas vayan más rápido</div>
        </div>
      </button>

      <button onclick="oneClickCleanAndRepairPC()" id="btnCleanPC" class="p-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-left transition flex items-center gap-3.5 shadow-sm">
        <span class="text-2xl">🧹</span>
        <div>
          <div class="font-bold text-sm md:text-base">Limpiar Basura y Actualizar mi PC</div>
          <div class="text-xs text-emerald-100">Limpieza profunda con BleachBit + actualización de drivers con SDIO</div>
        </div>
      </button>

      <button onclick="oneClickSpeedTest()" id="btnSpeedTest" class="p-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-left transition flex items-center gap-3.5 shadow-sm">
        <span class="text-2xl">⚡</span>
        <div>
          <div class="font-bold text-sm md:text-base">Medir Velocidad de Internet</div>
          <div class="text-xs text-indigo-100">Comprueba cuántos megas reales de bajada y subida tienes ahora</div>
        </div>
      </button>

      <button onclick="oneClickUndoLastChange()" id="btnUndo" class="p-4 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-white text-left transition flex items-center gap-3.5">
        <span class="text-2xl">⏪</span>
        <div>
          <div class="font-bold text-sm md:text-base">Deshacer Último Cambio</div>
          <div class="text-xs text-slate-300">Vuelve todo exactamente a como estaba antes con 1 clic</div>
        </div>
      </button>
    </div>

    <!-- Aviso de Resultado en Lenguaje Sencillo -->
    <div id="simpleStatusBanner" class="p-4 rounded-xl bg-slate-900/90 border border-slate-800 text-xs md:text-sm text-slate-200 leading-relaxed">
      ✅ <strong>Todo está en orden:</strong> Tu asistente está cuidando tu conexión y tu computador en segundo plano. Haz clic en cualquier botón de arriba si quieres acelerar o limpiar ahora mismo.
    </div>
  </div>

  <!-- Las 10 Especialidades del Ecosistema (Sub-Agentes Especializados) -->
  <div class="card p-5 space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div>
        <h2 id="ecosystemTitle" class="text-sm md:text-base font-bold text-white flex items-center gap-2">
          <span>🛡️</span> Las 10 Especialidades del Ecosistema
        </h2>
        <p id="ecosystemSub" class="text-xs text-[var(--muted)]">10 Sub-Agentes autónomos impulsados por librerías abiertas líderes para cuidar tu equipo</p>
      </div>
      <button onclick="loadSubagents()" class="text-xs px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition flex items-center gap-1">
        <span>🔄</span> <span>Actualizar</span>
      </button>
    </div>

    <div id="subagentsGrid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
      <!-- 10 Tarjetas generadas dinámicamente -->
    </div>
  </div>

  <!-- Chat Simple y Amigable con el Asistente -->
  <div class="card p-5 space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div>
        <h2 class="text-sm md:text-base font-bold text-white flex items-center gap-2">
          <span>💬</span> Pregúntale a tu Asistente (en palabras simples)
        </h2>
        <p class="text-xs text-[var(--muted)]">Sin palabras raras ni complicadas: pregúntale lo que necesites</p>
      </div>
      <div class="flex flex-wrap gap-1.5">
        <button onclick="sendQuickPrompt('¿Cómo está mi internet y mi PC ahora?')" class="text-xs px-3 py-1.5 rounded-full bg-slate-800 hover:bg-slate-700 text-blue-300 border border-slate-700 transition">
          🩺 ¿Cómo está todo?
        </button>
        <button onclick="sendQuickPrompt('Mide la velocidad de mi conexión')" class="text-xs px-3 py-1.5 rounded-full bg-slate-800 hover:bg-slate-700 text-emerald-300 border border-slate-700 transition">
          ⚡ Medir velocidad
        </button>
        <button onclick="sendQuickPrompt('Limpia la basura y repara mi computador')" class="text-xs px-3 py-1.5 rounded-full bg-slate-800 hover:bg-slate-700 text-amber-300 border border-slate-700 transition">
          🧹 Limpiar mi PC
        </button>
      </div>
    </div>

    <!-- Historial de Conversación -->
    <div id="chatHistory" class="bg-slate-950/80 rounded-xl border border-slate-800 p-4 h-72 overflow-y-auto space-y-3">
      <div class="flex items-start gap-3">
        <div class="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-sm shrink-0">🤖</div>
        <div class="bg-slate-900 border border-slate-800 rounded-2xl rounded-tl-none p-3.5 text-xs md:text-sm text-slate-200 max-w-2xl leading-relaxed">
          ¡Hola! Soy tu asistente automático. Cuido que tu internet no se corte y que tu computador esté limpio y rápido. Puedes usar los <strong>4 botones grandes de arriba</strong> o escribirme aquí abajo con tus propias palabras.
        </div>
      </div>
    </div>

    <!-- Caja para Escribir -->
    <div class="flex gap-2">
      <input type="text" id="chatInput" onkeydown="if(event.key==='Enter') sendMessage()" placeholder="Escríbeme aquí (por ejemplo: 'mi internet va lento', 'limpia mi PC', 'mide la velocidad')..." class="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-xs md:text-sm text-white focus:outline-none focus:border-blue-500">
      <button onclick="sendMessage()" id="btnSend" class="px-5 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs md:text-sm transition">
        Enviar
      </button>
    </div>
  </div>

  <script>
    let chatHistory = [];

    function setBanner(htmlText, borderClass = 'border-slate-800') {
      const b = document.getElementById('simpleStatusBanner');
      b.className = `p-4 rounded-xl bg-slate-900/90 border ${borderClass} text-xs md:text-sm text-slate-100 leading-relaxed`;
      b.innerHTML = htmlText;
    }

    function toggleSettingsModal() {
      document.getElementById('settingsDrawer').classList.toggle('hidden');
    }

    function toggleLicenseModal() {
      document.getElementById('licenseDrawer').classList.toggle('hidden');
    }

    async function loadLicenseStatus() {
      try {
        const res = await fetch('/api/license');
        const st = await res.json();
        document.getElementById('deviceIdText').textContent = st.device_id || 'PC-LOCAL';
        const badge = document.getElementById('planBadgeText');
        const detail = document.getElementById('planStatusDetail');
        if (st.is_pro) {
          badge.textContent = `Mi Plan: ${st.plan.toUpperCase()} ACTIVO`;
          detail.textContent = `${st.plan_name} (Ilimitado)`;
          detail.className = 'text-emerald-400';
        } else {
          badge.textContent = `Plan Gratis (${st.ai_queries_remaining} pruebas)`;
          detail.textContent = `Plan Gratis (${st.ai_queries_remaining} consultas restantes)`;
          detail.className = 'text-amber-400';
        }
      } catch (e) {}
    }

    async function activateLicenseKey(keyStr) {
      try {
        const res = await fetch('/api/license/activate', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({license_key: keyStr})
        });
        const data = await res.json();
        await loadLicenseStatus();
        setBanner(data.success ? `✅ <strong>${escapeHtml(data.message)}</strong>` : `⚠️ <strong>${escapeHtml(data.message)}</strong>`, data.success ? 'border-emerald-600' : 'border-rose-600');
      } catch (e) {}
    }

    function activateLicenseFromInput() {
      const k = document.getElementById('licenseKeyInput').value.trim();
      if (!k) return;
      activateLicenseKey(k);
    }

    function applyWorldLanguage(lang) {
      const dict = {
        es: {
          sub: 'Mantiene tu internet rápido y tu computador limpio automáticamente cada 10 minutos',
          boostTitle: 'Acelerar mi Internet',
          boostSub: 'Hace que las páginas, películas y videollamadas vayan más rápido',
          cleanTitle: 'Limpiar Basura y Actualizar mi PC',
          cleanSub: 'Limpieza profunda con BleachBit + actualización de drivers con SDIO',
          speedTitle: 'Medir Velocidad de Internet',
          speedSub: 'Comprueba cuántos megas reales de bajada y subida tienes ahora',
          undoTitle: 'Deshacer Último Cambio',
          undoSub: 'Vuelve todo exactamente a como estaba antes con 1 clic'
        },
        en: {
          sub: 'Keeps your internet fast and your PC clean automatically every 10 minutes',
          boostTitle: 'Boost My Internet',
          boostSub: 'Makes websites, streaming movies and video calls faster',
          cleanTitle: 'Clean Junk & Update My PC',
          cleanSub: 'Deep cleanup with BleachBit + automatic driver updates with SDIO',
          speedTitle: 'Test Internet Speed',
          speedSub: 'Check your real download and upload Mbps right now',
          undoTitle: 'Undo Last Change',
          undoSub: 'Restore everything back to how it was with 1 click'
        },
        pt: {
          sub: 'Mantém sua internet rápida e seu PC limpo automaticamente a cada 10 minutos',
          boostTitle: 'Acelerar Minha Internet',
          boostSub: 'Deixa sites, filmes e chamadas de vídeo mais rápidos',
          cleanTitle: 'Limpar Lixo e Atualizar Meu PC',
          cleanSub: 'Limpeza profunda com BleachBit + atualização de drivers com SDIO',
          speedTitle: 'Medir Velocidade da Internet',
          speedSub: 'Veja quantos megas reais de download e upload você tem agora',
          undoTitle: 'Desfazer Última Alteração',
          undoSub: 'Volta tudo exatamente como estava antes com 1 clique'
        }
      };
      const t = dict[lang] || dict.es;
      const btns = [
        ['btnBoostNet', '🚀', t.boostTitle, t.boostSub, 'text-blue-100'],
        ['btnCleanPC', '🧹', t.cleanTitle, t.cleanSub, 'text-emerald-100'],
        ['btnSpeedTest', '⚡', t.speedTitle, t.speedSub, 'text-indigo-100'],
        ['btnUndo', '⏪', t.undoTitle, t.undoSub, 'text-slate-300']
      ];
      btns.forEach(([id, icon, title, sub, subCls]) => {
        const el = document.getElementById(id);
        if (el) {
          el.innerHTML = `<span class="text-2xl">${icon}</span><div><div class="font-bold text-sm md:text-base">${title}</div><div class="text-xs ${subCls}">${sub}</div></div>`;
        }
      });
      const titleEl = document.getElementById('ecosystemTitle');
      const subEl = document.getElementById('ecosystemSub');
      if (titleEl) {
        if (lang === 'en') titleEl.innerHTML = '<span>🛡️</span> The 10 Ecosystem Specialties';
        else if (lang === 'pt') titleEl.innerHTML = '<span>🛡️</span> As 10 Especialidades do Ecossistema';
        else titleEl.innerHTML = '<span>🛡️</span> Las 10 Especialidades del Ecosistema';
      }
      if (subEl) {
        if (lang === 'en') subEl.textContent = '10 Autonomous Sub-Agents powered by leading open-source engines to safeguard your system';
        else if (lang === 'pt') subEl.textContent = '10 Sub-Agentes autônomos com motores abertos líderes para cuidar do seu computador';
        else subEl.textContent = '10 Sub-Agentes autónomos impulsados por librerías abiertas líderes para cuidar tu equipo';
      }
    }

    function onProviderChange() {
      const p = document.getElementById('cfgProvider').value;
      const m = document.getElementById('cfgModel');
      if (p === 'deepseek') m.value = 'deepseek-chat';
      else if (p === 'openai') m.value = 'gpt-4o';
      else if (p === 'ollama') m.value = 'llama3';
    }

    async function saveLlmSettings() {
      const provider = document.getElementById('cfgProvider').value;
      const model = document.getElementById('cfgModel').value;
      const apiKey = document.getElementById('cfgApiKey').value.trim();
      let baseUrl = 'https://api.deepseek.com';
      if (provider === 'openai') baseUrl = 'https://api.openai.com/v1';
      else if (provider === 'ollama') baseUrl = 'http://localhost:11434/v1';

      try {
        const payload = {provider, model, base_url: baseUrl};
        if (apiKey) payload.api_key = apiKey;
        await fetch('/api/llm/config', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload)
        });
        toggleSettingsModal();
        setBanner('✅ <strong>Listo:</strong> Configuración guardada correctamente.', 'border-emerald-700');
      } catch (e) {}
    }

    function escapeHtml(text) {
      const map = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'};
      return String(text || '').replace(/[&<>"']/g, m => map[m]);
    }

    function formatSimpleText(text) {
      return escapeHtml(text || '')
        .replace(/\\*\\*(.*?)\\*\\*/g, '<strong class="text-white">$1</strong>')
        .replace(/`([^`]+)`/g, '<strong class="text-blue-300">$1</strong>');
    }

    function appendMessage(sender, text) {
      const box = document.getElementById('chatHistory');
      const div = document.createElement('div');
      if (sender === 'user') {
        div.className = 'flex items-start justify-end gap-2.5';
        div.innerHTML = `
          <div class="bg-blue-600 text-white rounded-2xl rounded-tr-none p-3.5 text-xs md:text-sm max-w-xl">
            ${escapeHtml(text)}
          </div>
          <div class="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-xs font-bold text-white shrink-0">TÚ</div>
        `;
      } else {
        div.className = 'flex items-start gap-3';
        div.innerHTML = `
          <div class="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-sm shrink-0">🤖</div>
          <div class="bg-slate-900 border border-slate-800 rounded-2xl rounded-tl-none p-3.5 text-xs md:text-sm text-slate-200 max-w-2xl whitespace-pre-wrap leading-relaxed">${formatSimpleText(text)}</div>
        `;
      }
      box.appendChild(div);
      box.scrollTop = box.scrollHeight;
    }

    async function sendMessage() {
      const input = document.getElementById('chatInput');
      const text = input.value.trim();
      if (!text) return;

      appendMessage('user', text);
      input.value = '';
      document.getElementById('btnSend').disabled = true;

      const loadingDiv = document.createElement('div');
      loadingDiv.id = 'tempLoading';
      loadingDiv.className = 'flex items-start gap-3';
      loadingDiv.innerHTML = `
        <div class="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-sm shrink-0">🤖</div>
        <div class="bg-slate-900 border border-slate-800 rounded-2xl rounded-tl-none p-3.5 text-xs md:text-sm text-slate-400 italic">
          Revisando y haciendo lo que me pediste...
        </div>
      `;
      const box = document.getElementById('chatHistory');
      box.appendChild(loadingDiv);
      box.scrollTop = box.scrollHeight;

      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({message: text, history: chatHistory, language_mode: 'simple'})
        });
        const data = await res.json();
        const loadEl = document.getElementById('tempLoading');
        if (loadEl) loadEl.remove();

        chatHistory.push({role: 'user', content: text});
        chatHistory.push({role: 'assistant', content: data.reply});
        appendMessage('agent', data.reply);
        refreshSimpleCards();
      } catch (e) {
        const loadEl = document.getElementById('tempLoading');
        if (loadEl) loadEl.remove();
        appendMessage('agent', 'Perdón, ocurrió un problema al responder. Intenta de nuevo.');
      } finally {
        document.getElementById('btnSend').disabled = false;
      }
    }

    function sendQuickPrompt(promptText) {
      document.getElementById('chatInput').value = promptText;
      sendMessage();
    }

    async function toggleSentinel() {
      try {
        const res = await fetch('/api/sentinel/toggle', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({})});
        const st = await res.json();
        const txt = document.getElementById('sentinelText');
        const dot = document.getElementById('sentinelDot');
        if (st.enabled) {
          txt.textContent = 'Cuidado Automático: ACTIVO';
          dot.className = 'w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse';
        } else {
          txt.textContent = 'Cuidado Automático: PAUSADO';
          dot.className = 'w-2.5 h-2.5 rounded-full bg-slate-500';
        }
      } catch (e) {}
    }

    async function refreshSimpleCards() {
      try {
        const [diagRes, devRes] = await Promise.all([fetch('/api/diagnose'), fetch('/api/device/diagnose')]);
        const diag = await diagRes.json();
        const dev = await devRes.json();

        const healthEl = document.getElementById('healthMetric');
        if (diag.overall_health === 'healthy') {
          healthEl.textContent = 'Excelente';
          healthEl.className = 'text-2xl font-bold text-emerald-400';
        } else if (diag.overall_health === 'degraded') {
          healthEl.textContent = 'Algo Lento';
          healthEl.className = 'text-2xl font-bold text-amber-400';
        } else {
          healthEl.textContent = 'Con Problemas';
          healthEl.className = 'text-2xl font-bold text-rose-400';
        }
        document.getElementById('gatewayMetric').textContent = diag.gateway_reachable
          ? 'Conectado a tu router sin problemas'
          : 'Revisando conexión con tu router';

        const cf = (diag.latency_metrics && diag.latency_metrics['1.1.1.1']) || {};
        if (cf.avg_ms) {
          document.getElementById('latencyMetric').textContent = `Rápido (${cf.avg_ms} ms)`;
          document.getElementById('stabilityDesc').textContent = cf.packet_loss_percent === 0
            ? 'Sin cortes para llamadas, videos y juegos'
            : 'Se detectaron pequeños cortes que estamos cuidando';
        }

        if (dev.storage) {
          document.getElementById('devDiskFree').textContent = `${dev.storage.free_gb} GB Libres`;
        }
        if (dev.memory) {
          document.getElementById('devRamFree').textContent = `Memoria libre: ${dev.memory.available_ram_mb} MB (Todo fluido)`;
        }
      } catch (e) {}
    }

    async function oneClickBoostInternet() {
      setBanner('🚀 <strong>Acelerando tu Internet...</strong> Estamos eligiendo el camino más rápido para tus páginas web y limpiando conexiones antiguas.', 'border-blue-600');
      try {
        const res = await fetch('/api/optimize', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({execute: true})
        });
        const data = await res.json();
        await refreshSimpleCards();
        if (data.success && data.status !== 'REVERTED') {
          setBanner('✅ <strong>¡Tu Internet fue acelerado con éxito!</strong> Configuramos el buscador de páginas más rápido y guardamos una copia de seguridad automática.', 'border-emerald-600');
        } else {
          setBanner('⚠️ <strong>Ajuste revertido por seguridad (Zero NetLoss):</strong> Se detectó inestabilidad y restauramos automáticamente tu configuración anterior.', 'border-amber-600');
        }
      } catch (e) {
        setBanner('⚠️ No pudimos completar la aceleración en este momento.', 'border-rose-600');
      }
    }

    async function oneClickCleanAndRepairPC() {
      setBanner('🧹 <strong>Limpiando a fondo y verificando controladores...</strong> Borrando archivos basura de programas, juegos y navegadores (sin tocar tus claves) y revisando tus controladores.', 'border-emerald-600');
      try {
        const res = await fetch('/api/device/maintain', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({execute: true})
        });
        const data = await res.json();
        const tmp = data.temp_cleanup || {};
        const st = (data.post_maintenance && data.post_maintenance.storage) || {};
        const sdioInstalled = data.system_and_drivers && data.system_and_drivers.sdio_driver_engine && data.system_and_drivers.sdio_driver_engine.installed;
        const drvMsg = sdioInstalled ? 'la actualización automática de drivers con <strong>SDIO</strong>' : 'la verificación de controladores nativos del sistema';
        await refreshSimpleCards();
        setBanner(`✅ <strong>¡Tu PC quedó limpio y mantenido!</strong> Se borraron <strong>${tmp.cleaned_files || 0} archivos basura</strong> (${tmp.freed_mb || 0} MB liberados), se completó ${drvMsg} y ahora tienes <strong>${st.free_gb || '--'} GB libres</strong>.`, 'border-emerald-600');
      } catch (e) {
        setBanner('⚠️ Ocurrió un inconveniente durante la limpieza.', 'border-rose-600');
      }
    }

    async function oneClickSpeedTest() {
      setBanner('⚡ <strong>Midiendo la velocidad real de tu Internet...</strong> Espera unos segundos mientras probamos tu descarga y subida.', 'border-indigo-600');
      try {
        const res = await fetch('/api/speedtest');
        const d = await res.json();
        setBanner(`🚀 <strong>Resultado de tu Velocidad:</strong> Tienes <strong>${d.download_mbps} Mbps de Bajada</strong> (para ver películas y descargar rápido), <strong>${d.upload_mbps} Mbps de Subida</strong> (para videollamadas y enviar archivos) y una rapidez de respuesta de <strong>${d.ping_ms} ms</strong>.`, 'border-indigo-500');
      } catch (e) {
        setBanner('⚠️ No se pudo medir la velocidad en este instante.', 'border-rose-600');
      }
    }

    async function oneClickUndoLastChange() {
      setBanner('⏪ <strong>Restaurando tu última copia de seguridad...</strong>', 'border-amber-600');
      try {
        const sRes = await fetch('/api/snapshots');
        const sData = await sRes.json();
        const snaps = sData.snapshots || [];
        if (!snaps.length) {
          setBanner('ℹ️ <strong>No hay cambios recientes para deshacer:</strong> Tu configuración ya está en su estado original.', 'border-slate-700');
          return;
        }
        const lastSnap = snaps[snaps.length - 1];
        const rbRes = await fetch('/api/rollback', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({snapshot_id: lastSnap, execute: true})
        });
        const rbData = await rbRes.json();
        await refreshSimpleCards();
        if (rbData.success !== false) {
          setBanner('✅ <strong>¡Listo!</strong> Se deshizo el último cambio y tu configuración volvió a cómo estaba antes.', 'border-emerald-600');
        } else {
          setBanner('⚠️ No se encontró o no se pudo aplicar la copia de seguridad solicitada.', 'border-rose-600');
        }
      } catch (e) {
        setBanner('⚠️ No se pudo restaurar la copia de seguridad.', 'border-rose-600');
      }
    }

    async function loadSubagents() {
      try {
        const res = await fetch('/api/subagents');
        const list = await res.json();
        const container = document.getElementById('subagentsGrid');
        if (!container || !Array.isArray(list)) return;
        container.innerHTML = list.map(item => `
          <div class="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 flex flex-col justify-between space-y-2 hover:border-slate-700 transition">
            <div class="space-y-1.5">
              <div class="flex items-center justify-between">
                <span class="text-xl">${item.emoji}</span>
                <span id="badge-${item.id}" class="text-[10px] px-2 py-0.5 rounded-full font-bold bg-${item.color}-950 text-${item.color}-300 border border-${item.color}-700/60">${escapeHtml(item.status)}</span>
              </div>
              <div class="font-bold text-xs text-white leading-tight">${escapeHtml(item.name)}</div>
              <div class="text-[11px] text-slate-400 leading-snug line-clamp-2" title="${escapeHtml(item.motor)}">${escapeHtml(item.motor)}</div>
            </div>
            <button id="btn-sub-${item.id}" onclick="runSubagent('${item.id}')" class="mt-2 w-full py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition flex items-center justify-center gap-1 shadow-sm">
              <span>⚡</span> <span>Revisar</span>
            </button>
          </div>
        `).join('');
      } catch (e) {}
    }

    async function runSubagent(sid) {
      const btn = document.getElementById(`btn-sub-${sid}`);
      const badge = document.getElementById(`badge-${sid}`);
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span>⏳</span> <span>Revisando...</span>';
      }
      try {
        const res = await fetch('/api/subagents/run', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({id: sid, execute: true})
        });
        const data = await res.json();
        if (badge) {
          badge.textContent = 'Verificado';
          badge.className = 'text-[10px] px-2 py-0.5 rounded-full font-bold bg-emerald-950 text-emerald-300 border border-emerald-700/60';
        }
        if (data.summary) {
          setBanner(`✅ <strong>Sub-Agente Activo:</strong> ${escapeHtml(data.summary)}`, 'border-emerald-600');
          appendMessage('agent', data.summary);
        }
        await refreshSimpleCards();
      } catch (e) {
        setBanner('⚠️ No se pudo completar la acción del sub-agente.', 'border-rose-600');
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<span>⚡</span> <span>Revisar</span>';
        }
      }
    }

    window.onload = () => {
      refreshSimpleCards();
      loadLicenseStatus();
      loadSubagents();
    };
  </script>
</body>
</html>
"""


class OmniNetAPIHandler(BaseHTTPRequestHandler):
    """Zero-dependency HTTP/REST API and Web UI server for AI agent integration."""

    def log_message(self, format, *args):
        # Suppress noisy HTTP request logging
        pass

    def send_json(self, status: int, data: dict):
        body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html" or self.path.startswith("/?"):
            html_content = get_dashboard_html()
            body = html_content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/speedtest":
            self.send_json(200, measure_bandwidth_speed())
        elif self.path == "/health":
            self.send_json(200, {
                "status": "online",
                "service": "OmniNet AI Agent Pro",
                "version": VERSION,
                "platform": detect_platform().value
            })
        elif self.path == "/api/diagnose":
            diag = run_full_diagnostics()
            self.send_json(200, {
                "timestamp": diag.timestamp,
                "platform": diag.platform.value,
                "overall_health": diag.overall_health.value,
                "gateway_reachable": diag.gateway_reachable,
                "internet_reachable": diag.internet_reachable,
                "dns_resolving": diag.dns_resolving,
                "bufferbloat_grade": diag.bufferbloat_grade,
                "anomalies": diag.anomalies,
                "latency_metrics": {k: vars(v) for k, v in diag.latency_metrics.items()},
                "dns_benchmarks": [vars(b) for b in diag.dns_benchmarks]
            })
        elif self.path == "/api/bench-dns":
            bench = benchmark_all_resolvers()
            self.send_json(200, {"benchmarks": [vars(b) for b in bench]})
        elif self.path == "/api/snapshots":
            if os.path.exists(SNAPSHOT_DIR):
                snap_files = [
                    os.path.join(SNAPSHOT_DIR, f)
                    for f in os.listdir(SNAPSHOT_DIR)
                    if f.endswith(".json")
                ]
                snap_files.sort(key=lambda p: os.path.getmtime(p))
                snaps = [os.path.basename(p).replace(".json", "") for p in snap_files]
            else:
                snaps = []
            self.send_json(200, {"snapshots": snaps})
        elif self.path == "/api/incidents":
            sentinel = get_sentinel()
            self.send_json(200, {
                "incidents": [asdict(i) for i in sentinel.incidents[::-1]]
            })
        elif self.path == "/api/sentinel/status":
            sentinel = get_sentinel()
            self.send_json(200, sentinel.get_status())
        elif self.path == "/api/tasks":
            sched = get_task_scheduler()
            self.send_json(200, sched.get_status())
        elif self.path == "/api/sockets":
            self.send_json(200, inspect_active_sockets())
        elif self.path == "/api/wifi":
            self.send_json(200, inspect_wifi_and_nic())
        elif self.path == "/api/pmtu":
            self.send_json(200, discover_path_mtu("1.1.1.1"))
        elif self.path == "/api/arp":
            self.send_json(200, audit_arp_lan())
        elif self.path == "/api/device/diagnose":
            self.send_json(200, DeviceMaintenanceEngine().diagnose_all_device_faults())
        elif self.path == "/api/device/catalog":
            self.send_json(200, DeviceMaintenanceEngine().get_os_command_catalog("all"))
        elif self.path == "/api/license":
            self.send_json(200, get_license_manager().get_status())
        elif self.path == "/api/llm/config":
            cfg = load_llm_config()
            safe_cfg = {k: v for k, v in cfg.items() if k != "api_key"}
            safe_cfg["api_key_configured"] = bool(cfg.get("api_key"))
            if cfg.get("api_key"):
                safe_cfg["api_key_masked"] = cfg["api_key"][:4] + "..." + cfg["api_key"][-3:]
            self.send_json(200, safe_cfg)
        elif self.path == "/api/subagents":
            self.send_json(200, get_ecosystem_orchestrator().get_all_subagents_status())
        elif self.path == "/api/status":
            try:
                from netopt.elevation import is_elevated, elevation_status_str
                elevated = is_elevated()
                elev_str = elevation_status_str()
            except Exception:
                elevated = False
                elev_str = "unknown"
            sentinel = get_sentinel()
            self.send_json(200, {
                "version": VERSION,
                "platform": detect_platform().value,
                "admin_elevated": elevated,
                "elevation_status": elev_str,
                "sentinel_active": sentinel.running,
                "port": 8877,
            })
        else:
            self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > MAX_PAYLOAD_SIZE:
            self.send_json(413, {"error": "Payload Too Large (Máximo 1MB permitido)"})
            return

        post_data = self.rfile.read(content_length)
        payload = {}
        if post_data:
            try:
                payload = json.loads(post_data.decode("utf-8"))
            except Exception:
                pass

        # Autenticación y control de acceso local / CSRF (OMNI-003)
        client_ip = self.client_address[0]
        is_loopback = client_ip in ("127.0.0.1", "::1", "localhost")
        req_token = self.headers.get("X-OmniNet-Token") or payload.get("csrf_token")
        
        # Si la petición proviene de fuera de loopback y no posee el token, rechazar
        if not is_loopback and req_token != LOCAL_SESSION_TOKEN:
            self.send_json(403, {"error": "Acceso denegado: API local protegida (solo loopback o token válido)"})
            return

        execute = bool(payload.get("execute", False))
        hal = get_hal(dry_run=not execute)

        if self.path == "/api/optimize":
            optimizer = NetworkOptimizer(hal)
            plan = optimizer.generate_plan()
            success, logs = optimizer.execute_plan(plan, execute=execute)
            self.send_json(200, {
                "plan_id": plan.plan_id,
                "status": plan.status,
                "applied": execute,
                "success": success,
                "logs": logs
            })
        elif self.path == "/api/repair":
            repair = NetworkRepairEngine(hal)
            failure_type, triage_logs = repair.diagnose_and_triage()
            actions = repair.execute_triage_repair(failure_type, execute=execute)
            self.send_json(200, {
                "failure_type": failure_type,
                "triage_logs": triage_logs,
                "applied": execute,
                "actions": [vars(a) for a in actions]
            })
        elif self.path == "/api/rollback":
            snap_id = payload.get("snapshot_id", "")
            mgr = RollbackManager(hal)
            logs = mgr.rollback(snap_id, execute=execute)
            ok = bool(logs) and not any(str(l).startswith("ERROR:") for l in logs)
            self.send_json(200, {"snapshot_id": snap_id, "applied": execute and ok, "success": ok, "logs": logs})
        elif self.path == "/api/chat":
            msg = payload.get("message", "")
            history = payload.get("history", [])
            language_mode = payload.get("language_mode", "technical")
            gateway = LLMGateway()
            res = gateway.chat(msg, history=history, language_mode=language_mode)
            self.send_json(200, res)
        elif self.path == "/api/llm/config":
            gateway = LLMGateway()
            gateway.update_config(payload)
            safe_cfg = {k: v for k, v in gateway.config.items() if k != "api_key"}
            safe_cfg["api_key_configured"] = bool(gateway.config.get("api_key"))
            if gateway.config.get("api_key"):
                safe_cfg["api_key_masked"] = gateway.config["api_key"][:4] + "..." + gateway.config["api_key"][-3:]
            self.send_json(200, {"status": "saved", "config": safe_cfg})
        elif self.path == "/api/sentinel/toggle":
            sentinel = get_sentinel()
            requested_enabled = payload.get(
                "enabled",
                not sentinel.enabled
            )
            sentinel.enabled = bool(requested_enabled)
            if sentinel.enabled:
                sentinel.start()
            else:
                sentinel.stop()
            self.send_json(200, sentinel.get_status())
        elif self.path == "/api/sentinel/trigger":
            # Force trigger an immediate auto-heal check
            sentinel = get_sentinel()
            report = sentinel.check_health_and_auto_heal()
            self.send_json(200, {
                "triggered": True,
                "had_incident": report is not None,
                "report": asdict(report) if report else None,
                "status": sentinel.get_status()
            })
        elif self.path == "/api/tasks/trigger":
            sched = get_task_scheduler()
            res = sched.discover_and_schedule_cycle(execute=bool(payload.get("execute", False)))
            self.send_json(200, res)
        elif self.path == "/api/device/maintain":
            maint = DeviceMaintenanceEngine(hal)
            res = maint.run_full_device_maintenance(execute=execute)
            self.send_json(200, res)
        elif self.path == "/api/subagents/run":
            sid = payload.get("id", "")
            orch = get_ecosystem_orchestrator()
            res = orch.execute_subagent_by_id(sid, execute=execute)
            self.send_json(200, res)
        elif self.path == "/api/license/activate":
            lkey = payload.get("license_key", "")
            email = payload.get("email", "")
            res = get_license_manager().activate_license(lkey, email=email)
            self.send_json(200, res)
        else:
            self.send_json(404, {"error": "Endpoint not recognized"})


def start_api_server(port: int = 8877, open_browser: bool = True):
    bind_all = os.environ.get("OMNINET_BIND_ALL", "0").lower() in ("1", "true")
    host = "0.0.0.0" if bind_all else "127.0.0.1"
    url = f"http://127.0.0.1:{port}"
    try:
        server = ThreadingHTTPServer((host, port), OmniNetAPIHandler)
    except OSError:
        # Port 8877 is already running an active OmniNet server: just open the browser to it!
        print(f"[OmniNet] El servidor ya está activo en {url}. Abriendo navegador...")
        if open_browser:
            webbrowser.open(url)
        return

    # Start autonomous 10-minute task discovery & self-scheduler
    scheduler = get_task_scheduler()
    scheduler.start()
    print(f"[OmniNet] Revisión Automática de 10 Minutos Activa ({scheduler.interval_sec}s)")

    print(f"[OmniNet] Interfaz Web lista en: {url}")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[OmniNet] Cerrando servidor.")
        try:
            get_sentinel().stop()
        except Exception:
            pass
        server.server_close()


def interactive_menu():
    """Interactive CLI menu when double-clicked or run without arguments."""
    banner = f"""
===================================================================
     OMNINET AI AGENT PRO - AUTONOMOUS NETWORK OPTIMIZER v{VERSION}
   Universal Cross-Platform Internet Engine & Self-Healing Sentinel
===================================================================
  Platform: {detect_platform().value.upper()}
"""
    print(banner)
    print("1. Ejecutar Diagnóstico de Red (No destructivo)")
    print("2. Benchmark de Servidores DNS Mundiales")
    print("3. Generar Plan de Optimización (Simulación Dry-Run)")
    print("4. Diagnosticar y Diagnóstico de Triage de Fallos")
    print("5. Iniciar Servidor de Agente MCP (JSON-RPC stdio)")
    print("6. Iniciar Servidor REST API / Dashboard Web (Puerto 8877)")
    print("7. Salir")
    print("===================================================================")

    choice = input("\nSeleccione una opción (1-7): ").strip()
    if choice == "1":
        diag = run_full_diagnostics()
        print(format_diagnostics(diag))
    elif choice == "2":
        bench = benchmark_all_resolvers()
        print(f"\n{'Proveedor':<24} {'IP':<16} {'Latencia':<10} {'Éxito %':<10}")
        print("-" * 62)
        for b in bench:
            print(f"{b.provider:<24} {b.ip:<16} {b.avg_latency_ms:>6.2f}ms    {b.success_rate_percent:>5.1f}%")
    elif choice == "3":
        optimizer = NetworkOptimizer(get_hal(dry_run=True))
        plan = optimizer.generate_plan()
        success, logs = optimizer.execute_plan(plan, execute=False)
        print(f"\nPlan ID: {plan.plan_id}")
        print(f"Razonamiento:\n{plan.reasoning}")
        print("\nAcciones Propuestas (Simuladas):")
        for l in logs:
            print(f"  {l}")
    elif choice == "4":
        repair = NetworkRepairEngine(get_hal(dry_run=True))
        ft, logs = repair.diagnose_and_triage()
        print(f"\nResultado de Triage: {ft}")
        for l in logs:
            print(f"  - {l}")
    elif choice == "5":
        import mcp_server
        mcp_server.main()
    elif choice == "6":
        start_api_server(8877)
    else:
        print("Saliendo de OmniNet Pro.")
        sys.exit(0)


def main():
    if len(sys.argv) == 1:
        # When double-clicked or run without arguments, automatically launch the Web UI & open browser
        if sys.stdin and not sys.stdin.isatty() and not getattr(sys, "frozen", False):
            import mcp_server
            mcp_server.main()
            return
        start_api_server(8877, open_browser=True)
        return

    parser = argparse.ArgumentParser(description=f"OmniNet AI Agent Pro v{VERSION}")
    parser.add_argument("--version", action="version", version=f"OmniNet Pro {VERSION}")
    
    subparsers = parser.add_subparsers(dest="command")
    
    # Delegate to subcommands
    p_diag = subparsers.add_parser("diagnose", help="Run network diagnostics")
    p_diag.add_argument("--json", action="store_true")

    p_bench = subparsers.add_parser("benchmark-dns", help="Benchmark DNS servers")
    p_bench.add_argument("--json", action="store_true")

    p_opt = subparsers.add_parser("optimize", help="Formulate or apply network optimization")
    p_opt.add_argument("--apply", action="store_true", help="Apply modifications (Admin required)")
    p_opt.add_argument("--json", action="store_true")

    p_rep = subparsers.add_parser("repair", help="Run triage and heal connection")
    p_rep.add_argument("--apply", action="store_true", help="Apply repairs (Admin required)")
    p_rep.add_argument("--json", action="store_true")

    p_rb = subparsers.add_parser("rollback", help="Revert network configuration")
    p_rb.add_argument("--snapshot-id", type=str)
    p_rb.add_argument("--list", action="store_true")
    p_rb.add_argument("--apply", action="store_true")

    p_mcp = subparsers.add_parser("mcp", help="Run standard MCP JSON-RPC stdio server")

    p_serve = subparsers.add_parser("serve", help="Run HTTP REST API server")
    p_serve.add_argument("--port", type=int, default=8877)
    p_serve.add_argument("--no-browser", action="store_true")

    p_menu = subparsers.add_parser("menu", help="Run interactive CLI menu")

    p_daemon = subparsers.add_parser("daemon", help="Run persistent watcher daemon")
    p_daemon.add_argument("--interval", type=int, default=60)
    p_daemon.add_argument("--auto-heal", action="store_true")
    p_daemon.add_argument("--cycles", type=int, default=None)

    args = parser.parse_args()

    if args.command == "mcp":
        import mcp_server
        mcp_server.main()
    elif args.command == "serve":
        start_api_server(args.port, open_browser=not getattr(args, "no_browser", False))
    elif args.command == "menu":
        interactive_menu()
    else:
        # Re-use netopt.cli logic
        from netopt.cli import main as cli_main
        cli_main()


if __name__ == "__main__":
    main()

