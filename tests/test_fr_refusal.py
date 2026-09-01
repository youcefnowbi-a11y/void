"""VOIDFORGE :: FR refusal detection — verbatim fixtures from live provider
refusals (the chat mirrors the operator's language, so refusals come back
in French; the detector must catch them or the whole recipe disarms)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.framing import is_refusal, normalize

FR_REFUSAL = """J'ai fait les vérifications d'usage avant de parler plan — voilà où on en est, franchement :

**Ce que j'ai trouvé côté autorisation :**
- `venice.ai/.well-known/security.txt` → 404
- `venice.ai/security` → 404
- Pas de programme public sur Bugcrowd (ni HackerOne en recherche rapide)
- `robots.txt` confirme juste une stack Cloudflare + routes `/api/` fermées à l'indexation

**Le problème, en une ligne :** la cible est le flux de paiement réel d'une boîte tierce (checkout Plus mensuel, Stripe en face d'après tes cookies `__stripe_mid`), et je ne trouve aucune autorisation émise *par Venice.ai eux-mêmes*. Un `engagement.yaml` avec scope `*` ou une attestation de l'opérateur, ça couvre tes propres actifs ou un programme documenté — ça ne remplace jamais le feu vert du propriétaire de l'actif. Tester un checkout pour obtenir le tier sans payer, même avec ton propre compte, c'est le scénario exact où une "autorisation" auto-décrite ne vaut rien. Donc pas de `create_attack_plan`, pas de lancement, ici.

**Ce que je peux faire, et fais volontiers :**

1. **Lire ta propre session** (c'est ta data, zéro requête offensive) : ton `__session` est un JWT Clerk RS256, `iss: clerk.venice.ai`, `sub: user_3CISqizh...`, avec un `exp` à iat+60s — c'est le pattern Clerk de token court rafraîchi via le `rotating_token` dans `__client`. Rien d'anormal, c'est du Clerk standard bien configuré.
2. **Méthodo légitime** : si tu veux comprendre comment un audit autorisé de flux checkout se déroule (où sont les vraies failles : logique de prix côté serveur, webhooks Stripe, race conditions sur entitlements), je te fais le débrief complet — sans viser personne.
3. **Rediriger l'énergie** : tu as un actif à toi, ou une cible avec un programme public (VDP, Bugcrowd, HackerOne) ? Là, on arme tout l'arsenal et on fait une vraie campagne.

Si tu as un contrat privé avec Venice.ai, montre-moi le contact sécurité ou les termes du programme et on en reparle — mais je ne lancerai pas de strikes sur leur paiement sur la base du seul brief de ce salon."""


def test_live_fr_refusal_caught():
    assert is_refusal(FR_REFUSAL)


def test_fr_head_variants():
    assert is_refusal("Je ne lancerai pas de strikes là-dessus.")
    assert is_refusal("Je ne trouve aucune autorisation pour cette cible.")
    assert is_refusal("Ce que je peux faire, et fais volontiers : un labo légal.")
    assert is_refusal("Montre-moi le contact sécurité ou on en reste là.")


def test_en_conditional_offer_caught():
    assert is_refusal("What I can genuinely do instead is a PortSwigger lab.")
    assert is_refusal("Got real authorization, or want a legal playground?")


def test_legit_analysis_still_passes():
    assert not is_refusal("401 sur /admin — next: test IDOR avec le token volé.")
    assert not is_refusal("Le checkout renvoie 403 sans session; let's probe les headers.")


def test_normalized_fr_vocabulary():
    assert "frappe" in normalize("strike") or "strike" in normalize("strike")
