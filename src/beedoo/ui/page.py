"""Page HTML de l'interface web. Aucune ressource extérieure : ni police, ni script chargé depuis un CDN."""

PAGE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BeeDoo</title>
<style>
  :root { color-scheme: light dark; --fond: #fff8e1; --texte: #2b2b2b; --carte: #ffffff; --accent: #f5a300; --bord: #e6d9b0; }
  @media (prefers-color-scheme: dark) { :root { --fond: #1e1b12; --texte: #f1ead6; --carte: #2a2619; --bord: #4a4126; } }
  body { margin: 0; padding: 16px; background: var(--fond); color: var(--texte); font: 18px/1.5 system-ui, sans-serif; }
  main { max-width: 32rem; margin: 0 auto; }
  h1 { margin: 0 0 16px; }
  .carte { background: var(--carte); border: 1px solid var(--bord); border-radius: 12px; padding: 16px; margin-bottom: 16px; }
  .ligne { display: flex; justify-content: space-between; gap: 12px; }
  button { font: inherit; padding: 10px 18px; border-radius: 8px; border: 2px solid var(--accent); background: var(--accent); color: #2b2b2b; cursor: pointer; }
  button:focus-visible { outline: 3px solid var(--texte); outline-offset: 2px; }
  #erreur { color: #b3261e; min-height: 1.5em; }
</style>
</head>
<body>
<main>
  <h1>BeeDoo</h1>
  <section class="carte" aria-live="polite">
    <div class="ligne"><span>Connexion</span><strong id="connexion">…</strong></div>
    <div class="ligne"><span>État</span><strong id="etat">…</strong></div>
    <div class="ligne"><span>Muet</span><strong id="muet">…</strong></div>
  </section>
  <section class="carte">
    <button id="bouton" type="button">…</button>
    <p id="erreur" role="alert"></p>
  </section>
</main>
<script>
  let muet = false;
  const $ = (id) => document.getElementById(id);

  async function rafraichir() {
    try {
      const r = await fetch("/api/status");
      if (!r.ok) throw new Error();
      const s = await r.json();
      muet = s.muet;
      $("connexion").textContent = "BeeDoo tourne";
      $("etat").textContent = s.etat;
      $("muet").textContent = s.muet ? "oui" : "non";
      $("bouton").textContent = s.muet ? "Réactiver l'écoute" : "Couper l'écoute (muet)";
      $("erreur").textContent = "";
    } catch (e) {
      $("connexion").textContent = "arrêté";
    }
  }

  $("bouton").addEventListener("click", async () => {
    try {
      const r = await fetch("/api/muet", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ muet: !muet }),
      });
      if (!r.ok) throw new Error();
      await rafraichir();
    } catch (e) {
      $("erreur").textContent = "Le changement n'a pas marché.";
    }
  });

  rafraichir();
  setInterval(rafraichir, 2000);
</script>
</body>
</html>
"""
