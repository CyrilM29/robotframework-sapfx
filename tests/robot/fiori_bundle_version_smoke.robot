*** Settings ***
Documentation       Smoke du **bundle `__SAPFX` versionné** : la garde d'injection
...                 n'est plus « déjà présent » mais « présent ET de la même
...                 version », de sorte qu'un bundle périmé laissé dans la page
...                 soit REMPLACÉ au lieu d'être gardé à vie.
...
...                 Ce que prouve cette suite, et pourquoi elle existe : le vrai
...                 risque du versionnement n'est pas le remplacement, c'est ce
...                 que le remplacement fait aux HOOKS posés à l'injection
...                 (instrumentation de `fetch`/`XMLHttpRequest` pour
...                 `Wait For Ui5 Idle`, capture des `MessageToast`). Les
...                 réinstaller les doublerait (chaque requête comptée deux fois,
...                 donc une page jamais « au repos ») ; les abandonner les
...                 perdrait (une page toujours au repos, ce qui est pire :
...                 l'attente rend la main trop tôt et l'échec tombe ailleurs).
...                 Les trois tests mesurent donc, dans un vrai navigateur, le
...                 nombre d'incréments par requête, l'identité des enveloppes et
...                 la survie de l'état capté à travers un remplacement.
...
...                 La méthode est celle du cas réel vécu le 2026-08-24 : un
...                 bundle PÉRIMÉ est planté dans la page (ce que produit un
...                 hot-swap de la bibliothèque dans un serveur rf-mcp), puis un
...                 keyword ordinaire est appelé, ce qui déclenche la
...                 réinstallation.
...
...                 Hors ligne : aucun SAP, aucun réseau (fixture locale, et les
...                 requêtes émises pour compter sont volontairement vouées à
...                 l'échec : c'est leur COMPTAGE qui est mesuré, jamais leur
...                 réponse).
...
...                 Run:  robot --pythonpath src tests/robot/fiori_bundle_version_smoke.robot

Library             Browser
Library             SapFioriLibrary    ui5_timeout=10s
Library             OperatingSystem

Suite Setup         Open Fixture And Install Bundle
Suite Teardown      Close Browser


*** Variables ***
${HEADLESS}                 ${True}
# Version bidon plantée dans la page pour simuler un bundle périmé. Toute valeur
# qui n'est pas l'empreinte courante fait l'affaire : c'est bien la comparaison
# de version, et non une liste de versions connues, qui décide.
${VERSION_PERIMEE}          bundle-perime-0000
# Nombre d'incréments attendu pour UNE requête : un hook, une fois.
${INCREMENT_ATTENDU}        ${1}


*** Test Cases ***
Le bundle installe s annonce par une version et instrumente une seule fois
    [Documentation]    État de référence : le bundle en place porte une version
    ...    non vide, et chaque requête sortante est comptée EXACTEMENT une fois.
    ...
    ...    Le comptage se lit de façon synchrone, juste après l'émission : les
    ...    décréments passent par une micro-tâche, donc ce qu'on lit à cet
    ...    instant est le nombre d'incréments, c'est-à-dire le nombre
    ...    d'enveloppes empilées. Lire APRÈS le retour de la requête donnerait
    ...    zéro dans les deux cas, et ne prouverait rien.
    ${version}=    Lire La Version Du Bundle
    Should Not Be Empty    ${version}
    ...    msg=Le bundle installé n'expose aucune version : la garde ne peut plus distinguer deux bundles.
    ${fetchs}=    Compter Les Increments D Un Fetch
    Should Be Equal As Integers    ${fetchs}    ${INCREMENT_ATTENDU}
    ...    msg=Un fetch est compté ${fetchs} fois : l'instrumentation est empilée (page jamais au repos).
    ${xhrs}=    Compter Les Increments D Un Xhr
    Should Be Equal As Integers    ${xhrs}    ${INCREMENT_ATTENDU}
    ...    msg=Un XHR est compté ${xhrs} fois : l'instrumentation est empilée.

Un bundle perime dans la page est remplace au prochain appel
    [Documentation]    Le cœur du correctif. Un bundle d'une AUTRE version est
    ...    planté dans la page, puis un keyword ordinaire est appelé : la garde
    ...    d'injection doit reconnaître la version étrangère et réinstaller.
    ...
    ...    Avant le correctif, ce test échouait par construction : la garde
    ...    « déjà présent » sortait sans rien faire, et l'appel suivant tombait
    ...    sur le bundle périmé (« window.__SAPFX.<x> is not a function »), ce
    ...    que seul un rechargement de page réparait.
    ${attendue}=    Lire La Version Du Bundle
    Planter Un Bundle Perime
    ${perimee}=    Lire La Version Du Bundle
    Should Be Equal    ${perimee}    ${VERSION_PERIMEE}
    ...    msg=Le bundle périmé n'a pas été planté : le reste du test ne prouverait rien.
    Declencher Un Appel De Keyword
    ${apres}=    Lire La Version Du Bundle
    Should Be Equal    ${apres}    ${attendue}
    ...    msg=Le bundle périmé (${perimee}) survit à un appel de keyword : la garde d'injection ignore encore les versions.

Le remplacement ne double ni ne perd les hooks
    [Documentation]    La propriété qui coûterait cher à rater. Après le
    ...    remplacement du test précédent, on vérifie les trois faces de la même
    ...    exigence : les enveloppes de `fetch` et de `XMLHttpRequest` sont les
    ...    MÊMES fonctions qu'avant (donc pas ré-empilées), le porteur d'état est
    ...    le MÊME objet (donc rien n'est reparti de zéro), et un témoin déposé
    ...    dans la capture de toasts avant remplacement est toujours là après.
    ...
    ...    L'identité prouve l'absence de doublon, le comptage prouve que le hook
    ...    survivant alimente bien l'état COURANT : sans cette seconde mesure, un
    ...    hook orphelin nourrissant un état abandonné passerait pour intact.
    ${temoin}=    Set Variable    toast-temoin-avant-remplacement
    Memoriser Les Hooks Et Deposer Un Temoin    ${temoin}
    Planter Un Bundle Perime
    Declencher Un Appel De Keyword
    ${identiques}=    Les Hooks Sont Les Memes Qu Avant
    Should Be True    ${identiques}[fetch]
    ...    msg=L'enveloppe de fetch a été ré-empilée par la réinstallation.
    Should Be True    ${identiques}[xhr]
    ...    msg=L'enveloppe de XMLHttpRequest a été ré-empilée par la réinstallation.
    Should Be True    ${identiques}[state]
    ...    msg=Le porteur d'état a été remplacé : les hooks survivants nourrissent désormais un objet abandonné.
    ${toasts}=    Lire Les Toasts Captes
    Should Contain    ${toasts}    ${temoin}
    ...    msg=Le témoin déposé avant remplacement a disparu : la capture de toasts est repartie de zéro.
    ${fetchs}=    Compter Les Increments D Un Fetch
    Should Be Equal As Integers    ${fetchs}    ${INCREMENT_ATTENDU}
    ...    msg=Après remplacement, un fetch est compté ${fetchs} fois.
    ${xhrs}=    Compter Les Increments D Un Xhr
    Should Be Equal As Integers    ${xhrs}    ${INCREMENT_ATTENDU}
    ...    msg=Après remplacement, un XHR est compté ${xhrs} fois.


*** Keywords ***
Open Fixture And Install Bundle
    [Documentation]    Ouvre la fixture locale, puis provoque une première
    ...    injection du bundle par un appel de keyword ordinaire.
    ${fixture}=    Normalize Path    ${CURDIR}/fixtures/wc_fixture.html
    ${url}=    Evaluate    pathlib.Path(r"${fixture}").as_uri()    pathlib
    New Browser    chromium    headless=${HEADLESS}
    New Page    ${url}
    Wait For Function    () => window.__fixtureReady === true    timeout=20s
    Declencher Un Appel De Keyword

Declencher Un Appel De Keyword
    [Documentation]    Appelle un keyword de la bibliothèque, donc réinstalle le
    ...    bundle si nécessaire. Une lecture suffit : c'est le passage par
    ...    l'espace de noms qui compte, pas ce qu'on y lit.
    ${nb}=    Get Dom Match Count    css=body
    Should Be True    ${nb} >= 1

Lire La Version Du Bundle
    ${version}=    Evaluate JavaScript    ${None}
    ...    () => String((window.__SAPFX && window.__SAPFX.__v) || '')
    RETURN    ${version}

Planter Un Bundle Perime
    [Documentation]    Simule ce que laisse un hot-swap de bibliothèque : un
    ...    espace de noms `__SAPFX` d'une autre version, amputé de ses fonctions.
    Evaluate JavaScript    ${None}
    ...    () => { window.__SAPFX = { __v: '${VERSION_PERIMEE}' }; return true; }

Compter Les Increments D Un Fetch
    [Documentation]    Nombre d'incréments provoqués par UN fetch, lu de façon
    ...    synchrone. L'URL est volontairement inexistante : la requête échoue,
    ...    et c'est sans importance, seul son comptage est mesuré.
    ${compte}=    Evaluate JavaScript    ${None}
    ...    () => { const s = window.__SAPFX_STATE; if (!s) return -1; s.net.pending = 0;
    ...    try { fetch('sapfx-inexistant-' + Date.now()).catch(() => {}); } catch (e) {}
    ...    return s.net.pending; }
    RETURN    ${compte}

Compter Les Increments D Un Xhr
    [Documentation]    Même mesure pour `XMLHttpRequest`.
    ${compte}=    Evaluate JavaScript    ${None}
    ...    () => { const s = window.__SAPFX_STATE; if (!s) return -1; s.net.pending = 0;
    ...    try { const x = new XMLHttpRequest(); x.onerror = () => {};
    ...    x.open('GET', 'sapfx-inexistant-' + Date.now()); x.send(); } catch (e) {}
    ...    return s.net.pending; }
    RETURN    ${compte}

Memoriser Les Hooks Et Deposer Un Temoin
    [Documentation]    Met de côté l'identité des enveloppes et du porteur
    ...    d'état, et dépose un témoin dans la capture de toasts.
    [Arguments]    ${temoin}
    Evaluate JavaScript    ${None}
    ...    () => { window.__temoinHooks = { fetch: window.fetch,
    ...    xhr: XMLHttpRequest.prototype.send, state: window.__SAPFX_STATE };
    ...    window.__SAPFX_STATE.toasts.push({ text: '${temoin}', time: Date.now() });
    ...    return true; }

Les Hooks Sont Les Memes Qu Avant
    [Documentation]    Compare par IDENTITÉ, jamais par contenu : deux
    ...    enveloppes empilées se ressemblent, elles ne sont pas la même
    ...    fonction.
    ${verdict}=    Evaluate JavaScript    ${None}
    ...    () => { const t = window.__temoinHooks || {};
    ...    return { fetch: t.fetch === window.fetch,
    ...    xhr: t.xhr === XMLHttpRequest.prototype.send,
    ...    state: t.state === window.__SAPFX_STATE }; }
    RETURN    ${verdict}

Lire Les Toasts Captes
    ${textes}=    Evaluate JavaScript    ${None}
    ...    () => ((window.__SAPFX_STATE && window.__SAPFX_STATE.toasts) || []).map(t => String(t.text))
    RETURN    ${textes}
