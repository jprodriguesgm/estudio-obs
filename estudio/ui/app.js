// Estúdio — tela. Pergunta o estado ao app a cada segundo.
const $ = (s) => document.querySelector(s);
const MINI = new URLSearchParams(location.search).has("mini");
if (MINI) document.body.classList.add("mini");

let estado = null;
let assinaturaGrupos = "";
let assinaturaOpcoes = "";
let configAberta = false;

async function api(caminho, corpo) {
  const op = corpo === undefined ? {} : {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(corpo)};
  const r = await fetch(caminho, op);
  const d = await r.json().catch(() => ({erro: "Resposta inválida do app."}));
  if (!r.ok || d.erro) throw new Error(d.erro || `Erro ${r.status}`);
  return d;
}

function erro(msg) {
  const el = $("#erro-geral");
  if (!msg) { el.classList.add("hidden"); return; }
  el.textContent = msg; el.classList.remove("hidden");
  clearTimeout(erro._t); erro._t = setTimeout(() => el.classList.add("hidden"), 8000);
}

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
function tamanho(b) {
  if (b == null) return "—";
  if (b < 1024 * 1024) return (b / 1024).toFixed(0) + " KB";
  if (b < 1024 ** 3) return (b / 1024 / 1024).toFixed(1) + " MB";
  return (b / 1024 ** 3).toFixed(2) + " GB";
}
function duracao(s) {
  if (s == null) return "—";
  s = Math.round(s);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(x).padStart(2, "0");
}
const hora = (iso) => (iso || "").slice(11, 16);
const dataBR = (iso) => iso ? iso.slice(8, 10) + "/" + iso.slice(5, 7) : "";
const nomeCurto = (pasta) => pasta.replace(/^\d+_\d+\s+/, "");

// ------------------------------------------------------------------ desenho

function desenhar() {
  const e = estado;
  $("#versao").textContent = e.versao;
  $("#maquina").textContent = e.config.nome_maquina ? "· " + e.config.nome_maquina : "";
  document.title = e.gravando.length ? "● " + nomeCurto(e.gravando[e.gravando.length - 1].decisao.pasta) + " — Estúdio" : "Estúdio";

  const f = $("#faltando");
  if (e.faltando.length) {
    f.innerHTML = `Falta configurar: <b>${e.faltando.map(esc).join(", ")}</b>. Clique na engrenagem ⚙ (ou rode a simulação, que configura sozinha).`;
    f.classList.remove("hidden");
  } else if (!e.vigia_ok) {
    f.textContent = "O vigia da pasta parou de responder. Feche e abra o app de novo.";
    f.classList.remove("hidden");
  } else f.classList.add("hidden");

  desenharAgora(e);
  if (!MINI) { desenharAgenda(e); desenharGrupos(e); }
}

function desenharAgora(e) {
  const st = $("#agora-status");
  let html = "";
  if (e.gravando.length) {
    for (const g of e.gravando.slice(-1)) {   // OBS grava um arquivo por vez; mostra o mais recente
      const d = g.decisao;
      html += `<div class="grande"><span class="ponto"></span>Gravando agora: ${esc(nomeCurto(d.pasta))}</div>
        <div class="sub mono">${esc(g.arquivo)} · ${tamanho(g.tamanho)} · vai para <b>${esc(d.pasta)}</b></div>
        <div class="sub">${d.trocado ? "" : "Pela agenda: "}${esc(d.regra)}</div>`;
      if (d.aviso) html += `<div class="aviso">! ${esc(d.aviso)}</div>`;
      if (g.erro) html += `<div class="aviso">! ${esc(g.erro)}</div>`;
    }
  } else {
    const d = e.atual;
    html = `<div class="grande parado">Nada gravando. Uma gravação agora iria para: <b>&nbsp;${esc(d.pasta)}</b></div>
      <div class="sub">${esc(d.regra)}${d.trocado ? "" : ""}</div>`;
    if (d.aviso) html += `<div class="aviso">! ${esc(d.aviso)}</div>`;
  }
  for (const p of e.presos) html += `<div class="aviso">! ${esc(p.arquivo)}: ${esc(p.erro)}</div>`;
  if (e.troca) html += `<div class="trocado">↺ Troca ativa: o que a agenda mandaria para <b>${esc(e.troca.agenda_dizia)}</b> está indo para <b>${esc(e.troca.pasta)}</b>.</div>`;
  if (st.innerHTML !== html) st.innerHTML = html;

  const sig = JSON.stringify(e.opcoes);
  const sel = $("#troca-select");
  if (sig !== assinaturaOpcoes && document.activeElement !== sel) {
    const atual = sel.value;
    sel.innerHTML = e.opcoes.map((o) => `<option value="${esc(o)}">${esc(o)}</option>`).join("");
    if (e.opcoes.includes(atual)) sel.value = atual;
    assinaturaOpcoes = sig;
  }
  $("#troca-voltar").classList.toggle("hidden", !e.troca);
  $("#relogio").textContent = new Date().toLocaleTimeString("pt-BR", {hour: "2-digit", minute: "2-digit"});
}

function desenharAgenda(e) {
  const a = e.agenda;
  $("#agenda-arquivo").textContent = a.data ? "dia " + dataBR(a.data) : "";
  if (a.erro) { $("#agenda").innerHTML = `<div class="aviso">! ${esc(a.erro)}</div>`; return; }
  if (!a.eventos.length) { $("#agenda").innerHTML = `<div class="vazio">Nenhuma gravação na agenda.</div>`; return; }
  const chave = e.atual.chave;
  $("#agenda").innerHTML = a.eventos.map((ev) => `
    <div class="ev ${"ev" + ev.indice === chave ? "atual" : ""}">
      <span class="h">${ev.inicio}–${ev.fim}</span>
      <span><span class="cod">${esc(ev.codigo)}</span>${esc(ev.professor)}</span>
    </div>`).join("");
}

function desenharGrupos(e) {
  const box = $("#grupos");
  // não redesenha enquanto a pessoa está escolhendo num "Mover para"
  if (box.contains(document.activeElement) && document.activeElement.tagName === "SELECT") return;
  const sig = JSON.stringify([e.grupos, e.opcoes]);
  if (sig === assinaturaGrupos) return;
  assinaturaGrupos = sig;
  if (!e.grupos.length) { box.innerHTML = `<div class="vazio">Nenhuma gravação ainda. Quando o OBS terminar uma gravação, ela aparece aqui.</div>`; return; }
  box.innerHTML = e.grupos.map((g) => {
    const especial = !g.pode_subir;
    const durTotal = g.itens.reduce((s, i) => s + (i.duracao || 0), 0);
    let acao = "";
    const env = g.envio;
    if (especial) acao = `<span class="dica">não sobe — mova para o professor certo</span>`;
    else if (env && env.estado === "enviando") {
      const pct = env.total ? Math.round(100 * env.feito / env.total) : 0;
      acao = `<span class="dica">enviando… ${pct}%</span><div class="progresso"><i style="width:${pct}%"></i></div>`;
    } else if (g.enviado) acao = `<span class="estado enviado">✓ enviado, pode apagar</span>`;
    else acao = `<button class="btn principal pequeno" data-subir="${esc(g.pasta)}" data-dia="${esc(g.dia)}">Conferido, pode subir</button>`;
    if (env && env.msg && env.estado !== "enviando") acao = `<span class="dica">${esc(env.msg)}</span>` + acao;

    const itens = g.itens.map((i) => {
      const opcoes = e.opcoes.filter((o) => o !== g.pasta)
        .map((o) => `<option value="${esc(o)}">${esc(o)}</option>`).join("");
      const est = !i.existe && i.estado !== "enviado" ? `<span class="estado erro">arquivo sumiu</span> <button class="btn pequeno" data-esquecer="${i.id}">tirar da lista</button>`
        : `<span class="estado ${i.estado === "enviado" ? "enviado" : i.estado === "erro" ? "erro" : i.estado === "conferido" ? "conferido" : ""}">${esc(i.msg || i.estado)}</span>`;
      const mover = i.estado === "enviado" ? "" :
        `<select class="campo" data-mover="${i.id}"><option value="">Mover para…</option>${opcoes}</select>`;
      return `<div class="item">
        <span class="mono">${hora(i.inicio)}</span>
        <span class="arq" data-mostrar="${esc(i.caminho)}" title="Mostrar no Finder/Explorer">${esc(i.arquivo)}</span>
        <span class="num">${duracao(i.duracao)}</span>
        <span class="num">${tamanho(i.tamanho)}</span>
        <span class="regra">${esc(i.regra)}${i.aviso ? `<div class="aviso">! ${esc(i.aviso)}</div>` : ""}<div>${est}</div></span>
        <span>${mover}</span>
      </div>`;
    }).join("");
    return `<div class="grupo ${especial ? "especial" : ""}">
      <div class="grupo-topo"><span class="nome">${esc(g.pasta)}</span>
        <span class="info">${dataBR(g.data)} · ${g.itens.length} gravação(ões) · ${duracao(durTotal)}</span>
        <span class="acao">${acao}</span></div>${itens}</div>`;
  }).join("");
}

// ------------------------------------------------------------------ ações

$("#troca-btn").onclick = async () => {
  try { estado = {...estado, ...(await api("/api/trocar", {pasta: $("#troca-select").value}))}; desenhar(); }
  catch (x) { erro(x.message); }
};
$("#troca-voltar").onclick = async () => {
  try { estado = {...estado, ...(await api("/api/trocar", {pasta: null}))}; desenhar(); }
  catch (x) { erro(x.message); }
};
$("#abrir-mini").onclick = () => window.open("/?mini=1", "estudio-janelinha", "width=440,height=300");

$("#grupos").addEventListener("change", async (ev) => {
  const id = ev.target.dataset.mover;
  if (!id || !ev.target.value) return;
  const pasta = ev.target.value;
  ev.target.blur();
  try { estado = await api("/api/mover", {id, pasta}); assinaturaGrupos = ""; desenhar(); }
  catch (x) { erro(x.message); assinaturaGrupos = ""; desenhar(); }
});
$("#grupos").addEventListener("click", async (ev) => {
  const t = ev.target;
  try {
    if (t.dataset.subir) {
      t.disabled = true;
      estado = await api("/api/subir", {pasta: t.dataset.subir, dia: t.dataset.dia});
      assinaturaGrupos = ""; desenhar();
    } else if (t.dataset.esquecer) {
      estado = await api("/api/esquecer", {id: t.dataset.esquecer}); assinaturaGrupos = ""; desenhar();
    } else if (t.dataset.mostrar) {
      await api("/api/mostrar", {caminho: t.dataset.mostrar});
    }
  } catch (x) { erro(x.message); t.disabled = false; }
});

// configurações
function preencherConfig() {
  document.querySelectorAll(".cfg").forEach((c) => { c.querySelector("input").value = estado.config[c.dataset.campo] ?? ""; });
}
$("#abrir-config").onclick = () => {
  configAberta = !configAberta;
  $("#config").classList.toggle("hidden", !configAberta);
  if (configAberta) { preencherConfig(); $("#config").scrollIntoView({behavior: "smooth"}); }
};
$("#fechar-config").onclick = () => { configAberta = false; $("#config").classList.add("hidden"); };
document.querySelectorAll(".cfg .escolher").forEach((b) => b.onclick = async () => {
  const c = b.closest(".cfg");
  try {
    const r = await api("/api/escolher", {tipo: c.dataset.tipo === "arquivo" ? "arquivo" : "pasta"});
    if (r.caminho) c.querySelector("input").value = r.caminho;
  } catch (x) { erro(x.message); }
});
$("#salvar-config").onclick = async () => {
  const mudancas = {};
  document.querySelectorAll(".cfg").forEach((c) => {
    const v = c.querySelector("input").value.trim();
    mudancas[c.dataset.campo] = c.dataset.tipo === "numero" ? Number(v) : (v || null);
  });
  try { estado = await api("/api/config", {mudancas}); desenhar(); configAberta = false; $("#config").classList.add("hidden"); }
  catch (x) { erro(x.message); }
};

// ------------------------------------------------------------------ laço

async function atualizar() {
  try {
    estado = await api("/api/estado");
    desenhar();
  } catch (x) {
    $("#faltando").textContent = "O app está fechado. Abra o Estúdio de novo (dois cliques em Abrir Estudio.command).";
    $("#faltando").classList.remove("hidden");
  }
  setTimeout(atualizar, 1000);
}
atualizar();
