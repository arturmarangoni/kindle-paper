// Despertador do jornal: um Worker do Cloudflare que, nos horários de wrangler.toml, manda o GitHub rodar a
// impressão (.github/workflows/paper.yml). O agendamento do próprio GitHub atrasa e pula execuções; este não.
//
// GH_TOKEN é um token "fine-grained" do GitHub com acesso só a este repositório e permissão Actions: Read and write.
// Ele fica guardado como segredo no Cloudflare (npx wrangler secret put GH_TOKEN), nunca no código.

const DISPATCH = "https://api.github.com/repos/arturmarangoni/kindle-paper/actions/workflows/paper.yml/dispatches";

async function print(env) {
  const r = await fetch(DISPATCH, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GH_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "kindle-paper-cron",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  // 204 = impressão pedida. Qualquer outra resposta aparece como erro nos logs do Worker.
  if (r.status !== 204) throw new Error(`GitHub respondeu ${r.status}: ${await r.text()}`);
  console.log("impressão pedida ao GitHub");
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(print(env));
  },
  // Abrir o endereço do Worker no navegador só mostra que ele existe; não dispara nada.
  async fetch() {
    return new Response("Despertador do A&I Press: pede uma impressão ao GitHub nos horários agendados.\n");
  },
};
