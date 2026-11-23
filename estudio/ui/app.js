// Estúdio — tela. Agenda → professor → gravar → subir → voltar. Pergunta o estado ao app a cada segundo.
const $ = (s) => document.querySelector(s);
const MINI = new URLSearchParams(location.search).has("mini");
if (MINI) document.body.classList.add("mini");

let estado = null;
const assinaturas = {};
let configAberta = false;
let fechado = false;

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
  clearTimeout(erro._t); erro._t = setTimeout(() => el.classList.add("hidden"), 9000);
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
// desenha só quando mudou (e nunca enquanto a pessoa está escolhendo numa lista)
function mudou(nome, dados, caixa) {
  if (caixa && caixa.contains(document.activeElement) && document.activeElement.tagName === "SELECT") return false;
  const sig = JSON.stringify(dados);
  if (assinaturas[nome] === sig) return false;
  assinaturas[nome] = sig;
  return true;
}
const redesenhar = () => { for (const k in assinaturas) delete assinaturas[k]; };

// ------------------------------------------------------------------ desenho

function desenhar() {
  const e = estado;
  $("#versao").textContent = e.versao;
  $("#maquina").textContent = e.config.nome_maquina ? "· " + e.config.nome_maquina : "";
  const gr = e.gravando[e.gravando.length - 1];
  document.title = gr ? "● " + nomeCurto(gr.decisao.pasta) + " — Estúdio" : "Estúdio";

  const f = $("#faltando");
  if (e.faltando.length) {
    f.innerHTML = `Falta configurar: <b>${e.faltando.map(esc).join(", ")}</b>. Clique na engrenagem ⚙.`;
    f.classList.remove("hidden");
  } else if (!e.vigia_ok) {
    f.textContent = "O vigia da pasta parou de responder. Feche e abra o app de novo.";
    f.classList.remove("hidden");
  } else f.classList.add("hidden");

  desenharAgora(e);
  if (MINI) return;
  const naSessao = !!e.sessao;
  $("#tela-agenda").classList.toggle("hidden", naSessao);
  $("#tela-sessao").classList.toggle("hidden", !naSessao);
  if (naSessao) desenharSessao(e); else desenharAgenda(e);
}

function desenharAgora(e) {
  const st = $("#agora-status");
  let html = "";
  const g = e.gravando[e.gravando.length - 1];      // OBS grava um arquivo por vez
  if (g) {
    const d = g.decisao;
    html += `<div class="grande"><span class="ponto"></span>Gravando agora: ${esc(nomeCurto(d.pasta))}</div>
      <div class="sub mono">${esc(g.arquivo)} · ${tamanho(g.tamanho)} · vai para <b>${esc(d.pasta)}</b></div>
      <div class="sub">${d.trocado ? "Escolhido à mão" : "Pelo horário: " + esc(d.regra)}</div>`;
    if (d.aviso) html += `<div class="aviso">! ${esc(d.aviso)}</div>`;
    if (g.erro) html += `<div class="aviso">! ${esc(g.erro)}</div>`;
  } else {
    const d = e.atual;
    html = `<div class="grande parado">Nada gravando. A próxima gravação vai para: <b>${esc(d.pasta)}</b></div>
      <div class="sub">${d.trocado ? "escolhido à mão" : esc(d.regra)}</div>`;
    if (d.aviso) html += `<div class="aviso">! ${esc(d.aviso)}</div>`;
  }
  for (const p of e.presos) html += `<div class="aviso">! ${esc(p.arquivo)}: ${esc(p.erro)}</div>`;
  if (st.innerHTML !== html) st.innerHTML = html;

  const sel = $("#troca-select");
  if (mudou("opcoes", e.opcoes, $("#troca-det"))) {
    const atual = sel.value;
    sel.innerHTML = e.opcoes.map((o) => `<option value="${esc(o)}">${esc(o)}</option>`).join("");
    if (e.opcoes.includes(atual)) sel.value = atual;
  }
  $("#troca-voltar").classList.toggle("hidden", !e.troca);
  $("#relogio").textContent = new Date().toLocaleTimeString("pt-BR", {hour: "2-digit", minute: "2-digit"});
}

function grupoDe(e, pasta, dia) { return e.grupos.find((g) => g.pasta === pasta && g.dia === dia); }
const diaHoje = (e) => e.agenda.data ? e.agenda.data.replace(/-/g, " ") : "";

function desenharAgenda(e) {
  const a = e.agenda;
  const pd = a.fonte === "pastas do dia";
  const semana = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
  const diaTxt = a.data ? semana[new Date(a.data + "T12:00:00").getDay()] + " " + dataBR(a.data) : "";
  $("#agenda-titulo").textContent = e.outro_dia ? `Agenda de ${diaTxt}` : `Agenda de hoje${diaTxt ? " · " + diaTxt : ""}`;
  $("#agenda-info").textContent = a.info || "";
  $("#atualizar-agenda").classList.toggle("hidden", !pd);
  $("#nav-dia").classList.toggle("hidden", !pd);
  $("#dia-hoje").classList.toggle("hidden", !e.outro_dia);
  if (a.data && document.activeElement !== $("#dia-escolha")) $("#dia-escolha").value = a.data;
  const av = $("#aviso-outro-dia");
  if (e.outro_dia) {
    av.innerHTML = `Você está vendo a agenda de <b>${esc(diaTxt)}</b>, não a de hoje. Se escolher um professor aqui, as gravações de agora vão para ele, na pasta do dia <b>${esc(a.data.replace(/-/g, " "))}</b>.`;
    av.classList.remove("hidden");
  } else av.classList.add("hidden");

  const caixa = $("#agenda");
  const dados = [a, e.atual.chave, e.troca, e.grupos.map((g) => [g.pasta, g.dia, g.itens.length, g.enviado, g.envio && g.envio.estado])];
  if (mudou("agenda", dados, caixa)) {
    if (a.carregando) caixa.innerHTML = `<div class="vazio">Carregando a agenda do Pastas do dia… (leva alguns segundos)</div>`;
    else if (a.erro) caixa.innerHTML = `<div class="aviso">! ${esc(a.erro)}</div>`;
    else if (!a.eventos.length) caixa.innerHTML = `<div class="vazio">Nenhuma gravação na agenda de hoje.</div>`;
    else {
      const dia = diaHoje(e);
      caixa.innerHTML = a.eventos.map((ev) => cartaoEvento(e, ev, dia)).join("") +
        (a.canceladas.length ? `<div class="canceladas">Canceladas: ${a.canceladas.map((c) => esc(c.hora + " " + c.professor)).join(" · ")}</div>` : "");
    }
  }

  // grupos que não são de nenhum horário de hoje
  const pastasHoje = new Set(a.eventos.map((ev) => ev.pasta));
  const outros = e.grupos.filter((g) => !(pastasHoje.has(g.pasta) && g.dia === diaHoje(e)));
  $("#caixa-outras").classList.toggle("hidden", !outros.length);
  if (mudou("outras", [outros, e.opcoes], $("#outras"))) $("#outras").innerHTML = outros.map((g) => htmlGrupo(e, g)).join("");
}

function cartaoEvento(e, ev, dia) {
  const atual = e.atual.chave === ev.id;
  const escolhido = e.troca && e.troca.pasta === ev.pasta || (!e.troca && atual);
  const g = grupoDe(e, ev.pasta, dia);
  let chips = "";
  if (atual) chips += `<span class="chip agora">agora</span>`;
  if (escolhido) chips += `<span class="chip escolhido">próxima gravação vai para cá</span>`;
  if (e.agenda.fonte === "pastas do dia") {
    chips += ev.tem_pasta_drive ? `<span class="chip ok">pasta no Drive</span>` : `<span class="chip ruim">sem pasta no Drive</span>`;
    if (ev.pasta_dia_url) chips += `<span class="chip ok">pasta do dia criada</span>`;
  }
  if (g) {
    const n = g.itens.length;
    chips += g.enviado ? `<span class="chip ok">✓ ${n} enviada(s)</span>` : `<span class="chip">${n} gravação(ões)</span>`;
  }
  let codigo = esc(ev.codigo || "sem código");
  if (ev.candidatos.length > 1) {
    codigo = `<select class="campo codigo" data-codigo-ev="${esc(ev.id)}">` + ev.candidatos.map((c, i) =>
      `<option value="${i}" ${i === ev.escolha ? "selected" : ""}>${esc(c.codigo)}${c.tem_pasta ? "" : " (sem pasta)"}</option>`).join("") + `</select>`;
  }
  const sub = [ev.tipo, ev.disciplina].filter(Boolean).map(esc).join(" · ");
  return `<div class="evento ${atual ? "atual" : ""} ${escolhido ? "escolhido" : ""}">
    <div class="ev-hora mono">${ev.inicio}<small>até ${ev.fim}</small></div>
    <div class="ev-meio">
      <div class="ev-nome">${esc(ev.professor)}</div>
      <div class="ev-sub">${sub || "&nbsp;"}</div>
      <div class="ev-chips"><span class="cod">${codigo}</span>${chips}</div>
      ${ev.aviso ? `<div class="aviso">! ${esc(ev.aviso)}</div>` : ""}
    </div>
    <div class="ev-acao"><button class="btn ${atual || escolhido ? "principal" : ""}" data-selecionar="${esc(ev.id)}">${g ? "Abrir" : "Gravar com este professor"}</button></div>
  </div>`;
}

function desenharSessao(e) {
  const s = e.sessao, ev = s.evento;
  const cab = `<div class="ses-nome">${esc(ev.professor)}</div>
    <div class="ses-sub mono">${esc(ev.pasta)} / ${esc(s.dia)} / Footage</div>
    <div class="ses-sub">${esc(ev.inicio)}–${esc(ev.fim)} · ${[ev.tipo, ev.disciplina].filter(Boolean).map(esc).join(" · ")}</div>
    ${ev.aviso ? `<div class="aviso">! ${esc(ev.aviso)}</div>` : ""}`;
  if (mudou("ses-cab", cab)) $("#sessao-cab").innerHTML = cab;
  const link = ev.pasta_dia_url || ev.pasta_url;
  const links = link ? `<a href="${esc(link)}" target="_blank" rel="noopener">Abrir no Drive ↗</a>` : "";
  if ($("#sessao-links").innerHTML !== links) $("#sessao-links").innerHTML = links;
  const g = grupoDe(e, ev.pasta, s.dia);
  if (mudou("ses-grupo", [g, e.opcoes], $("#sessao-grupo"))) {
    $("#sessao-grupo").innerHTML = g ? htmlGrupo(e, g)
      : `<div class="vazio">Nenhuma gravação ainda. Grave no OBS: quando parar, o vídeo aparece aqui.</div>`;
  }
}

function htmlGrupo(e, g) {
  const especial = !g.pode_subir;
  const durTotal = g.itens.reduce((s, i) => s + (i.duracao || 0), 0);
  let acao = "";
  const env = g.envio;
  const ocupado = env && ["transcrevendo", "enviando", "conferindo"].includes(env.estado);
  if (especial) acao = `<span class="dica">não sobe — mova para o professor certo</span>`;
  else if (ocupado) {
    const total = g.itens.length;
    const nomes = {transcrevendo: "1/3 transcrevendo…",
                   enviando: `2/3 subindo… ${env.pct || 0}% · ${env.arquivos_ok || 0} de ${total} vídeo(s) no Drive`,
                   conferindo: "3/3 conferindo no Drive…"};
    const pct = env.estado === "transcrevendo" ? 5 : env.estado === "conferindo" ? 100 : (env.pct || 0);
    const det = env.estado === "enviando" ? (env.detalhe || "") : env.estado === "transcrevendo" ? (env.msg || "") : "";
    acao = `<div class="andamento"><span class="dica">${nomes[env.estado]}</span><div class="progresso"><i style="width:${pct}%"></i></div>${det ? `<span class="dica">${esc(det)}</span>` : ""}</div>`;
  } else if (g.enviado) acao = `<span class="estado enviado">✓ enviado, pode apagar</span><button class="btn pequeno" data-subir="${esc(g.pasta)}" data-dia="${esc(g.dia)}" title="Sobe de novo (o que já está igual no Drive não sobe outra vez)">Subir de novo</button>`;
  else acao = `<button class="btn principal pequeno" data-subir="${esc(g.pasta)}" data-dia="${esc(g.dia)}" title="Transcreve, sobe e confere no Drive">${env && env.estado === "erro" ? "Tentar de novo" : "Conferido, pode subir"}</button>`;
  let rodape = "";
  if (env && env.msg && env.estado !== "enviando") {
    const cls = env.estado === "ok" ? "ok" : env.estado === "erro" ? "erro" : "info";
    rodape = `<div class="grupo-msg ${cls}">${esc(env.msg)}${env.etapa ? " · " + esc(env.etapa) : ""}</div>`;
  }
  const itens = g.itens.map((i) => {
    const opcoes = e.opcoes.filter((o) => o !== g.pasta).map((o) => `<option value="${esc(o)}">${esc(o)}</option>`).join("");
    const est = !i.existe && i.estado !== "enviado" ? `<span class="estado erro">arquivo sumiu</span> <button class="btn pequeno" data-esquecer="${i.id}">tirar da lista</button>`
      : `<span class="estado ${i.estado === "enviado" || /✓/.test(i.msg || "") ? "enviado" : i.estado === "erro" ? "erro" : i.estado === "conferido" ? "conferido" : ""}">${esc(i.msg || i.estado)}</span>`;
    const mover = i.estado === "enviado" ? "" : `<select class="campo" data-mover="${i.id}"><option value="">Mover para…</option>${opcoes}</select>`;
    return `<div class="item">
      <span class="mono">${hora(i.inicio)}</span>
      <span class="arq" data-mostrar="${esc(i.caminho)}" title="Mostrar no Finder/Explorer">${esc(i.arquivo)}</span>
      <span class="num">${duracao(i.duracao)}</span>
      <span class="num">${tamanho(i.tamanho)}</span>
      <span class="regra">${esc(i.regra)}${i.aviso ? `<div class="aviso">! ${esc(i.aviso)}</div>` : ""}<div>${est}</div></span>
      <span>${mover}</span>
    </div>`;
  }).join("");
  const tirar = ocupado ? "" : `<button class="btn pequeno fraco" data-tirar="${esc(g.pasta)}" data-dia="${esc(g.dia)}" title="Some com este grupo da tela. Os arquivos continuam na pasta.">Tirar da lista</button>`;
  return `<div class="grupo ${especial ? "especial" : ""}">
    <div class="grupo-topo"><span class="nome">${esc(g.pasta)}</span>
      <span class="info">${dataBR(g.data)} · ${g.itens.length} gravação(ões) · ${duracao(durTotal)}</span>
      <span class="acao">${acao}${tirar}</span></div>${rodape}${itens}</div>`;
}

// ------------------------------------------------------------------ ações

async function acao(caminho, corpo, botao) {
  if (botao) botao.disabled = true;
  try { estado = await api(caminho, corpo); redesenhar(); desenhar(); return estado; }
  catch (x) { erro(x.message); redesenhar(); desenhar(); }
  finally { if (botao) botao.disabled = false; }
}

$("#troca-btn").onclick = () => acao("/api/trocar", {pasta: $("#troca-select").value});
$("#troca-voltar").onclick = () => acao("/api/trocar", {pasta: null});
$("#abrir-mini").onclick = () => window.open("/?mini=1", "estudio-janelinha", "width=440,height=260");
$("#fechar-app").onclick = async (ev) => {
  const b = ev.target;
  if (!b.dataset.confirmar) {
    b.dataset.confirmar = "1"; b.textContent = "Clique de novo para fechar";
    setTimeout(() => { delete b.dataset.confirmar; b.textContent = "Fechar o Estúdio"; }, 4000);
    return;
  }
  try { await api("/api/sair", {}); } catch (x) { /* já fechou */ }
  fechado = true;
  $("#janela").classList.add("hidden"); $("#fechado").classList.remove("hidden");
};
$("#voltar").onclick = () => acao("/api/voltar", {});
$("#dia-ant").onclick = (ev) => acao("/api/dia", {passo: -1}, ev.target);
$("#dia-prox").onclick = (ev) => acao("/api/dia", {passo: 1}, ev.target);
$("#dia-hoje").onclick = (ev) => acao("/api/dia", {}, ev.target);
$("#dia-escolha").onchange = (ev) => { if (ev.target.value) acao("/api/dia", {data: ev.target.value}); };
$("#atualizar-agenda").onclick = (ev) => { ev.target.textContent = "Atualizando…"; acao("/api/atualizar_agenda", {}, ev.target).then(() => ev.target.textContent = "Atualizar"); };

document.addEventListener("change", (ev) => {
  const t = ev.target;
  if (t.dataset.mover && t.value) { const pasta = t.value; t.blur(); acao("/api/mover", {id: t.dataset.mover, pasta}); }
  else if (t.dataset.codigoEv) { t.blur(); acao("/api/codigo", {id: t.dataset.codigoEv, codigo: Number(t.value)}); }
});
document.addEventListener("click", async (ev) => {
  const t = ev.target.closest("button, .arq");
  if (!t) return;
  if (t.dataset.selecionar) {
    t.textContent = "Criando as pastas…";
    const r = await acao("/api/selecionar", {id: t.dataset.selecionar}, t);
    if (r && r.selecionado && r.selecionado.avisos.length) erro("Atenção: " + r.selecionado.avisos.join("; ") + ".");
  } else if (t.dataset.subir) acao("/api/subir", {pasta: t.dataset.subir, dia: t.dataset.dia}, t);
  else if (t.dataset.esquecer) acao("/api/esquecer", {id: t.dataset.esquecer}, t);
  else if (t.dataset.tirar) {
    if (t.dataset.confirmar) acao("/api/esquecer_grupo", {pasta: t.dataset.tirar, dia: t.dataset.dia}, t);
    else { t.dataset.confirmar = "1"; t.textContent = "Clique de novo para tirar (arquivos ficam)"; setTimeout(() => { delete t.dataset.confirmar; t.textContent = "Tirar da lista"; }, 4000); }
  }
  else if (t.dataset.mostrar) { try { await api("/api/mostrar", {caminho: t.dataset.mostrar}); } catch (x) { erro(x.message); } }
});

// configurações
function campoDe(c) { return c.querySelector("select") || c.querySelector("input"); }
function preencherConfig() {
  document.querySelectorAll(".cfg").forEach((c) => {
    const el = campoDe(c), v = estado.config[c.dataset.campo];
    if (c.dataset.tipo === "caixa") el.checked = !!v; else el.value = v ?? "";
  });
  const en = estado.envio;
  $("#destino-input").placeholder = en.destino_padrao || "ex.: drive:Gravações IEC/Teste Estúdio";
  const snd = en.subir_no_drive;
  $("#destino-dica").className = "dica";
  $("#destino-dica").textContent = snd
    ? `Subir no Drive encontrado: conexão "${snd.remoto}", pasta "${snd.raiz || "(raiz)"}"${snd.email ? ", conta " + snd.email : ""}. Cada professor vira uma pasta dentro do destino: <destino>/26_xxx Professor/AAAA MM DD/Footage.`
    : "Não achei o Subir no Drive neste computador. Preencha o destino (conexão do rclone:pasta).";
  $("#transcribe-dica").textContent = en.transcribe ? "Transcrição: " + en.transcribe : "Sem transcrição neste computador: as gravações sobem sem transcrever.";
  visibilidadeEnvio();
}
function visibilidadeEnvio() {
  const modo = document.querySelector('.cfg[data-campo="envio_modo"] select').value;
  document.querySelectorAll(".so-rclone").forEach((x) => x.classList.toggle("hidden", modo !== "rclone"));
  document.querySelectorAll(".so-pasta").forEach((x) => x.classList.toggle("hidden", modo !== "pasta"));
}
document.querySelector('.cfg[data-campo="envio_modo"] select').onchange = visibilidadeEnvio;
function lerConfig() {
  const mudancas = {};
  document.querySelectorAll(".cfg").forEach((c) => {
    const el = campoDe(c);
    if (c.dataset.tipo === "caixa") mudancas[c.dataset.campo] = el.checked;
    else if (c.dataset.tipo === "numero") mudancas[c.dataset.campo] = Number(el.value);
    else if (["rclone_destino", "pastas_do_dia_url", "nome_maquina", "rclone_exe"].includes(c.dataset.campo)) mudancas[c.dataset.campo] = el.value.trim();
    else mudancas[c.dataset.campo] = el.value.trim() || null;
  });
  return mudancas;
}
$("#testar").onclick = async () => {
  const d = $("#destino-dica"); d.className = "dica"; d.textContent = "Testando…";
  try { const r = await api("/api/testar", {mudancas: lerConfig()}); d.className = "dica ok"; d.textContent = "✓ " + r.msg; }
  catch (x) { d.className = "dica ruim"; d.textContent = "✗ " + x.message; }
};
$("#testar-pd").onclick = async () => {
  const d = $("#pd-dica"); d.className = "dica"; d.textContent = "Testando…";
  try { const r = await api("/api/testar_pd", {url: $("#pd-input").value}); $("#pd-input").value = r.url; d.className = "dica ok"; d.textContent = "✓ " + r.msg + " Clique em Salvar."; }
  catch (x) { d.className = "dica ruim"; d.textContent = "✗ " + x.message; }
};
$("#abrir-config").onclick = () => {
  configAberta = !configAberta;
  $("#config").classList.toggle("hidden", !configAberta);
  if (configAberta) { preencherConfig(); $("#config").scrollIntoView({behavior: "smooth"}); }
};
$("#fechar-config").onclick = () => { configAberta = false; $("#config").classList.add("hidden"); };
document.querySelectorAll(".cfg .escolher").forEach((b) => b.onclick = async () => {
  const c = b.closest(".cfg");
  try {
    const r = await api("/api/escolher", {tipo: c.dataset.tipo.startsWith("arquivo") ? "arquivo" : "pasta", exe: c.dataset.tipo === "arquivo-exe"});
    if (r.caminho) c.querySelector("input").value = r.caminho;
  } catch (x) { erro(x.message); }
});
$("#salvar-config").onclick = async () => {
  const r = await acao("/api/config", {mudancas: lerConfig()});
  if (r) { configAberta = false; $("#config").classList.add("hidden"); }
};

// ------------------------------------------------------------------ laço

async function atualizar() {
  if (fechado) return;
  try {
    estado = await api("/api/estado");
    desenhar();
  } catch (x) {
    $("#faltando").textContent = "O Estúdio está fechado. Abra de novo (dois cliques no app Estúdio).";
    $("#faltando").classList.remove("hidden");
  }
  setTimeout(atualizar, 1000);
}
atualizar();
