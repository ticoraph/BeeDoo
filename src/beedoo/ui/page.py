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
  li { flex-wrap: wrap; display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid var(--bord); }
  li span { flex: 1; }
  input { font: inherit; padding: 8px; border-radius: 8px; border: 1px solid var(--bord); background: var(--carte); color: var(--texte); min-width: 0; flex: 1; }
  label { display: block; margin-bottom: 4px; }
  button.petit { padding: 4px 10px; background: transparent; color: var(--texte); border-color: var(--bord); }
  .note { font-size: 0.85rem; opacity: 0.75; margin-bottom: 0; }
  .reglage { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
  .reglage label { flex: 0 0 9rem; margin: 0; }
  .reglage input[type=range] { flex: 1; padding: 0; }
  .reglage input[type=checkbox] { flex: 0; width: 1.2rem; height: 1.2rem; }
  select { font: inherit; padding: 6px; border-radius: 8px; border: 1px solid var(--bord); background: var(--carte); color: var(--texte); }
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
  <section class="carte" aria-live="polite">
    <h2>Ce que BeeDoo voit</h2>
    <p id="vision">…</p>
  </section>
  <section class="carte" aria-live="polite">
    <h2>Dernière conversation</h2>
    <p><strong>BeeDoo a entendu :</strong> <span id="entendu">—</span></p>
    <p><strong>BeeDoo a dit :</strong> <span id="dit">—</span></p>
    <p class="note">Gardé en mémoire seulement, effacé à la fin de la conversation.</p>
    <p id="memoire-etat"><strong>Mémoire :</strong> <span id="memoire-texte">—</span></p>
  </section>
  <section class="carte">
    <h2>Réglages</h2>
    <div class="reglage"><label for="suivi">Suivi du visage</label>
      <input id="suivi" type="checkbox"><span>la tête me suit du regard</span></div>
    <div class="reglage"><label for="volume">Volume du robot</label>
      <input id="volume" type="range" min="0" max="100" step="5"><output id="volume-valeur"></output></div>
    <div class="reglage"><label for="vitesse">Vitesse de la voix</label>
      <select id="vitesse"><option value="0.7">Lente</option><option value="1">Normale</option><option value="1.3">Rapide</option></select></div>
    <div class="reglage"><label for="voix">Voix</label><select id="voix"></select></div>
    <div class="reglage"><label for="ville">Ma ville (météo)</label>
      <input id="ville" maxlength="80" placeholder="Ville" autocomplete="off"></div>
    <button id="test-voix" type="button">Écouter la voix</button>
    <p id="reglages-info" aria-live="polite"></p>
  </section>
  <section class="carte">
    <h2>Mini-applications</h2>
    <ul id="miniapps"></ul>
    <p class="note">Dis par exemple « une blague de Toto » ou « quel temps fait-il ? ».</p>
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
      <div class="reglage"><input id="consent-ajout" type="checkbox">
        <label for="consent-ajout" style="flex:1">Cette personne accepte que BeeDoo se souvienne de ce qu'elle dit</label></div>
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

  function phraseVision(v) {
    const min = v.min_taille;
    if (v.statut !== "pause" && v.statut !== "indisponible" && v.age > 15) {
      return "La caméra ne répond plus (dernière image il y a " + Math.round(v.age) + " s).";
    }
    switch (v.statut) {
      case "reconnu": return "Je te reconnais : " + (v.nom || "") + ".";
      case "inconnu": return "Je vois un visage, mais je ne le connais pas. Ajoute-toi dans « Personnes » ci-dessous.";
      case "trop_petit": return "Je te vois, mais tu es trop loin. Approche-toi (ton visage fait " + v.taille + " px, il en faut au moins " + min + ").";
      case "aucun_visage": return "Je ne vois personne. Mets-toi face à moi, le visage bien éclairé.";
      case "ambigu": return "Je vois un visage mais j'hésite entre deux personnes. Approche-toi un peu.";
      case "pause": return "Je regarde pour l'ajout d'une personne (voir plus bas).";
      case "pas_d_image": return "Je ne reçois pas d'image de la caméra.";
      case "erreur": return "Je n'arrive pas à analyser l'image (voir le terminal).";
      case "inactif": return "Je me réveille…";
      default: return "La vision n'est pas disponible.";
    }
  }

  async function chargerVision() {
    try {
      const r = await fetch("/api/vision");
      $("vision").textContent = phraseVision(await r.json());
    } catch (e) {
      $("vision").textContent = "BeeDoo ne répond plus.";
    }
  }

  function phraseMemoire(m) {
    if (!m || m.etat === "personne") return "je ne sais pas à qui je parle, rien n'est gardé.";
    if (m.etat === "desactivee") return "désactivée pour toi, rien n'est gardé. Pour l'activer, coche « Accepte que BeeDoo se souvienne » dans Personnes.";
    const dernier = m.dernier ? " Dernière mise à jour : " + m.dernier.ajoutes + " souvenir(s) ajouté(s), " + m.dernier.retires + " retiré(s)." : "";
    if (m.etat === "extraction") return "je réfléchis à ce qu'il faut retenir…";
    if (m.etat === "enregistre") return "activée. " + m.phrases + " échange(s) enregistré(s) dans le fichier de la conversation. Je retiens les faits après " + m.pause + " s de silence, ou à la fin." + dernier;
    return "activée, je retiendrai ce que tu me dis." + dernier;
  }

  async function chargerEchange() {
    try {
      const r = await (await fetch("/api/echange")).json();
      const e = r.echange;
      $("entendu").textContent = e && e.entendu ? e.entendu : "—";
      $("dit").textContent = e && e.dit ? e.dit : "—";
      $("memoire-texte").textContent = phraseMemoire(r.memoire);
    } catch (err) {}
  }

  let reglagesChargesUneFois = false;
  async function chargerReglages() {
    try {
      const r = await (await fetch("/api/reglages")).json();
      const voix = $("voix");
      if (!voix.options.length) for (const v of r.voix_possibles) voix.add(new Option(v, v));
      voix.value = r.voix;
      $("suivi").checked = r.suivi;
      if (document.activeElement !== $("ville")) $("ville").value = r.ville;
      $("vitesse").value = String(r.vitesse >= 1.15 ? 1.3 : r.vitesse <= 0.85 ? 0.7 : 1);
      $("volume").disabled = r.volume === null;
      if (r.volume !== null) { $("volume").value = r.volume; $("volume-valeur").textContent = r.volume + " %"; }
      else $("reglages-info").textContent = "Le volume du robot n'est pas joignable.";
      reglagesChargesUneFois = true;
    } catch (err) {
      $("reglages-info").textContent = "Réglages indisponibles.";
    }
  }

  async function changerReglage(corps) {
    try {
      await envoyer("POST", "/api/reglages", corps);
      $("reglages-info").textContent = "";
    } catch (err) {
      $("reglages-info").textContent = err.message;
      chargerReglages();
    }
  }

  $("volume").addEventListener("input", () => { $("volume-valeur").textContent = $("volume").value + " %"; });
  $("volume").addEventListener("change", () => changerReglage({ volume: Number($("volume").value) }));
  $("vitesse").addEventListener("change", () => changerReglage({ vitesse: Number($("vitesse").value) }));
  $("suivi").addEventListener("change", () => changerReglage({ suivi: $("suivi").checked }));
  $("ville").addEventListener("change", () => changerReglage({ ville: $("ville").value }));
  $("voix").addEventListener("change", () => changerReglage({ voix: $("voix").value }));
  $("test-voix").addEventListener("click", async () => {
    try { await envoyer("POST", "/api/test-voix"); $("reglages-info").textContent = ""; }
    catch (err) { $("reglages-info").textContent = err.message; }
  });

  async function chargerMiniapps() {
    try {
      const liste = (await (await fetch("/api/miniapps")).json()).miniapps;
      const zone = $("miniapps");
      zone.textContent = "";
      for (const m of liste) {
        const li = document.createElement("li");
        const case_ = document.createElement("input");
        case_.type = "checkbox"; case_.checked = m.active; case_.id = "app-" + m.nom;
        case_.style.flex = "0 0 auto";
        case_.addEventListener("change", async () => {
          try { await envoyer("POST", "/api/miniapps/" + encodeURIComponent(m.nom), { active: case_.checked }); }
          catch (e) { $("reglages-info").textContent = e.message; }
        });
        const etiquette = document.createElement("label");
        etiquette.htmlFor = case_.id; etiquette.textContent = m.titre; etiquette.style.margin = "0";
        li.append(case_, etiquette);
        zone.appendChild(li);
      }
    } catch (e) {}
  }

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

  function volets(p) {
    const d = document.createElement("details");
    d.style.flexBasis = "100%";
    const resume = document.createElement("summary");
    resume.textContent = p.memoire
      ? "Souvenirs : " + p.faits + " retenus, " + p.conversations + " conversation(s) gardée(s)"
      : "Souvenirs : désactivés";
    const accord = document.createElement("input");
    accord.type = "checkbox"; accord.checked = p.memoire; accord.id = "memoire-" + p.id;
    const etiquette = document.createElement("label");
    etiquette.htmlFor = accord.id; etiquette.style.display = "inline";
    etiquette.textContent = " Accepte que BeeDoo se souvienne de ce qu'elle dit";
    const zone = document.createElement("textarea");
    zone.rows = 6; zone.style.width = "100%"; zone.maxLength = 4200;
    zone.setAttribute("aria-label", "Souvenirs, un par ligne");
    const info = document.createElement("p");
    info.className = "note";
    const enregistrer = document.createElement("button");
    enregistrer.type = "button"; enregistrer.className = "petit"; enregistrer.textContent = "Enregistrer les souvenirs";
    const vider = document.createElement("button");
    vider.type = "button"; vider.className = "petit"; vider.textContent = "Effacer les souvenirs";
    const url = "/api/personnes/" + encodeURIComponent(p.id);

    d.addEventListener("toggle", async () => {
      if (!d.open) return;
      try { zone.value = (await (await fetch(url + "/souvenirs")).json()).faits.join("\\n"); }
      catch (e) { info.textContent = "Souvenirs indisponibles."; }
    });
    accord.addEventListener("change", async () => {
      try { await envoyer("PUT", url + "/memoire", { accepte: accord.checked }); info.textContent = accord.checked ? "Enregistré : BeeDoo se souviendra." : "BeeDoo ne retient plus rien de cette personne."; }
      catch (e) { info.textContent = e.message; }
    });
    enregistrer.addEventListener("click", async () => {
      try {
        await envoyer("PUT", url + "/souvenirs", { faits: zone.value.split("\\n") });
        info.textContent = "Souvenirs enregistrés.";
      } catch (e) { info.textContent = e.message; }
    });
    let arme = false;
    vider.addEventListener("click", async () => {
      if (!arme) {
        arme = true; vider.textContent = "Sûr ? Tout effacer";
        setTimeout(() => { arme = false; vider.textContent = "Effacer les souvenirs"; }, 4000);
        return;
      }
      try { await envoyer("DELETE", url + "/souvenirs"); zone.value = ""; info.textContent = "Souvenirs effacés (visage conservé)."; }
      catch (e) { info.textContent = e.message; }
      arme = false; vider.textContent = "Effacer les souvenirs";
    });
    const aide = document.createElement("p");
    aide.className = "note";
    aide.textContent = "Un souvenir par ligne. Sans cette case cochée, BeeDoo ne retient rien et n'utilise aucun souvenir.";
    d.append(resume, aide, accord, etiquette, zone, enregistrer, vider, info);
    return d;
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
    li.append(nom, renommer, effacer, volets(p));
    return li;
  }

  async function chargerPersonnes() {
    try {
      const r = await fetch("/api/personnes");
      const d = await r.json();
      const liste = $("personnes");
      const enEdition = liste.querySelector("details[open]") || liste.contains(document.activeElement);
      if (!enEdition) {  // on ne reconstruit pas la liste sous les doigts de quelqu'un qui modifie un souvenir
        liste.textContent = "";
        for (const p of d.personnes) liste.appendChild(ligne(p));
        if (!d.personnes.length) {
          const vide = document.createElement("li");
          vide.textContent = "Personne pour l'instant.";
          liste.appendChild(vide);
        }
      }
      const e = d.enrolement;
      const enCours = e && e.etat === "en_cours";
      $("ajouter").disabled = !d.camera || enCours;
      if (enCours) {
        let conseil = "Regarde BeeDoo et tourne doucement la tête.";
        if (e.derniere === "aucun_visage") conseil = "Je ne te vois pas : mets-toi face à moi.";
        if (e.derniere === "trop_petit") conseil = "Tu es trop loin : approche-toi (visage " + e.taille + " px, il en faut " + e.min_taille + ").";
        $("personnes-info").textContent = conseil + " Images valides : " + e.ajoutes + "/" + e.total + ".";
      } else if (e && e.etat === "termine") {
        $("personnes-info").textContent = "C'est fait : " + e.ajoutes + " images enregistrées. Éloigne-toi un instant, puis reviens : je te saluerai.";
      } else if (e && e.etat === "echec") {
        $("personnes-info").textContent = "Pas assez d'images valides (" + e.ajoutes + "). Approche-toi, éclaire ton visage et réessaie.";
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
      await envoyer("POST", "/api/personnes", { prenom: $("prenom").value, memoire: $("consent-ajout").checked });
      $("prenom").value = "";
    } catch (e) {
      $("personnes-info").textContent = e.message;
    }
    chargerPersonnes();
  });

  chargerGestes();
  chargerMiniapps();
  chargerReglages();
  chargerEchange();
  chargerVision();
  chargerPersonnes();
  rafraichir();
  setInterval(rafraichir, 2000);
  setInterval(chargerPersonnes, 2000);
  setInterval(chargerVision, 1000);
  setInterval(chargerEchange, 1500);
</script>
</body>
</html>
"""
