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
  h2 { margin: 0 0 12px; font-size: 1.1rem; }
  .boutons { display: flex; flex-wrap: wrap; gap: 8px; }
  button:disabled { opacity: 0.5; cursor: default; }
  ul { list-style: none; margin: 0 0 12px; padding: 0; }
  li { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid var(--bord); }
  li span { flex: 1; }
  input { font: inherit; padding: 8px; border-radius: 8px; border: 1px solid var(--bord); background: var(--carte); color: var(--texte); min-width: 0; flex: 1; }
  label { display: block; margin-bottom: 4px; }
  button.petit { padding: 4px 10px; background: transparent; color: var(--texte); border-color: var(--bord); }
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
    <h2>Gestes</h2>
    <div id="gestes" class="boutons"></div>
    <p id="gestes-info"></p>
  </section>
  <section class="carte">
    <h2>Personnes que BeeDoo connaît</h2>
    <ul id="personnes"></ul>
    <form id="ajout" autocomplete="off">
      <label for="prenom">Ajouter une personne</label>
      <div class="ligne">
        <input id="prenom" maxlength="40" placeholder="Prénom" required>
        <button id="ajouter" type="submit">Ajouter</button>
      </div>
    </form>
    <p id="personnes-info" aria-live="polite"></p>
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
      $("bouton").textContent = s.muet ? "Réactiver l'écoute et la parole" : "Muet : ne plus écouter ni parler";
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

  async function chargerGestes() {
    try {
      const r = await fetch("/api/gestes");
      const g = await r.json();
      const zone = $("gestes");
      zone.textContent = "";
      for (const nom of g.gestes) {
        const b = document.createElement("button");
        b.type = "button";
        b.textContent = nom.replace("_", " ");
        b.disabled = !g.disponible;
        b.addEventListener("click", async () => {
          const rep = await fetch("/api/geste", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ nom }),
          });
          $("gestes-info").textContent = rep.status === 409 ? "Un geste est déjà en cours." : "";
        });
        zone.appendChild(b);
      }
      if (!g.disponible) $("gestes-info").textContent = "Robot non connecté.";
    } catch (e) {
      $("gestes-info").textContent = "Gestes indisponibles.";
    }
  }

  async function envoyer(methode, url, corps) {
    const r = await fetch(url, {
      method: methode,
      headers: { "Content-Type": "application/json" },
      body: corps ? JSON.stringify(corps) : undefined,
    });
    if (!r.ok) {
      let detail = "";
      try { detail = (await r.json()).detail || ""; } catch (e) {}
      throw new Error(detail || "erreur " + r.status);
    }
  }

  function ligne(p) {
    const li = document.createElement("li");
    const nom = document.createElement("span");
    nom.textContent = p.nom + " (" + p.empreintes + " empreintes)";
    const renommer = document.createElement("button");
    renommer.type = "button"; renommer.className = "petit"; renommer.textContent = "Renommer";
    renommer.addEventListener("click", () => {
      const champ = document.createElement("input");
      champ.value = p.nom; champ.maxLength = 40;
      li.replaceChild(champ, nom);
      renommer.textContent = "Valider";
      renommer.onclick = async () => {
        try { await envoyer("PATCH", "/api/personnes/" + encodeURIComponent(p.id), { prenom: champ.value }); }
        catch (e) { $("personnes-info").textContent = e.message; }
        chargerPersonnes();
      };
    });
    const effacer = document.createElement("button");
    effacer.type = "button"; effacer.className = "petit"; effacer.textContent = "Effacer";
    let arme = false;
    effacer.addEventListener("click", async () => {
      if (!arme) {
        arme = true; effacer.textContent = "Sûr ?";
        setTimeout(() => { arme = false; effacer.textContent = "Effacer"; }, 4000);
        return;
      }
      try { await envoyer("DELETE", "/api/personnes/" + encodeURIComponent(p.id)); }
      catch (e) { $("personnes-info").textContent = e.message; }
      chargerPersonnes();
    });
    li.append(nom, renommer, effacer);
    return li;
  }

  async function chargerPersonnes() {
    try {
      const r = await fetch("/api/personnes");
      const d = await r.json();
      const liste = $("personnes");
      liste.textContent = "";
      for (const p of d.personnes) liste.appendChild(ligne(p));
      if (!d.personnes.length) {
        const vide = document.createElement("li");
        vide.textContent = "Personne pour l'instant.";
        liste.appendChild(vide);
      }
      const e = d.enrolement;
      const enCours = e && e.etat === "en_cours";
      $("ajouter").disabled = !d.camera || enCours;
      if (enCours) {
        $("personnes-info").textContent = "Regarde BeeDoo et tourne doucement la tête… " + e.fait + "/" + e.total;
      } else if (e && e.etat === "termine") {
        $("personnes-info").textContent = "C'est fait : " + e.ajoutes + " empreintes enregistrées.";
      } else if (e && e.etat === "echec") {
        $("personnes-info").textContent = "Aucun visage trouvé. Approche-toi et réessaie.";
      } else if (!d.camera) {
        $("personnes-info").textContent = "Caméra non connectée.";
      }
    } catch (err) {
      $("personnes-info").textContent = "Liste indisponible.";
    }
  }

  $("ajout").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      await envoyer("POST", "/api/personnes", { prenom: $("prenom").value });
      $("prenom").value = "";
    } catch (e) {
      $("personnes-info").textContent = e.message;
    }
    chargerPersonnes();
  });

  chargerGestes();
  chargerPersonnes();
  rafraichir();
  setInterval(rafraichir, 2000);
  setInterval(chargerPersonnes, 2000);
</script>
</body>
</html>
"""
