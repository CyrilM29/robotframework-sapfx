*** Settings ***
Documentation       Smoke du **moteur Web Components** (`Resolve/Click/Fill Wc …`) contre
...                 la fixture locale `fixtures/wc_fixture.html`, une page « pur UI5
...                 Web Components » SANS runtime UI5 (registre vide : les moteurs
...                 role/xpath sont aveugles, c'est précisément le cas d'usage du 3e
...                 moteur : home SuccessFactors et apps ui5-webcomponents). Prouve :
...                 le matching type court/tag complet Y COMPRIS les tags scopés
...                 (`ui5-button-x1b2`), le matching attributs/texte, le clic et la
...                 saisie à travers un shadow root ouvert, le repli `wc=` de
...                 `Resolve Ui5 With Fallback`, et la capture WC du recorder web.
...                 Hors ligne : aucun SAP, aucun réseau (fixture 100 % locale).
...
...                 Run:  robot --pythonpath src tests/robot/fiori_wc_smoke.robot

Library             Browser
Library             SapFioriLibrary    ui5_timeout=10s
Library             OperatingSystem

Suite Setup         Open Wc Fixture
Suite Teardown      Close Browser


*** Variables ***
${HEADLESS}         ${True}


*** Test Cases ***
Short Tag Matches Plain And Scoped Custom Elements
    [Documentation]    `tag=Button` doit matcher les <ui5-button> ET le tag scopé
    ...                <ui5-button-x1b2> (scoping UI5 WC) ; un tag complet aussi.
    ...                Le 4e est l'hôte du shadow root de `deepBar` : depuis le
    ...                parcours profond (2026-08-26), les hôtes imbriqués comptent.
    ${count}=    Get Wc Match Count    tag=Button
    Should Be Equal As Integers    ${count}    4
    ${count}=    Get Wc Match Count    tag=ui5-button
    Should Be Equal As Integers    ${count}    4
    ${count}=    Get Wc Match Count    tag=Input
    Should Be Equal As Integers    ${count}    1
    Wc Control Should Be Visible    tag=Button    text=Scoped save

Short Tag Matches Both Spellings Of A Two Word Component
    [Documentation]    Un type court en DEUX mots doit atteindre les deux
    ...                orthographes qu'emploie UI5 Web Components : collée
    ...                (`ui5-shellbar`, la vraie barre shell d'un launchpad Work
    ...                Zone) et avec tirets (`ui5-side-navigation`). Relevé live
    ...                le 2026-08-24 : `tag=ShellBar` ne matchait rien, le type
    ...                court étant converti en `shell-bar` puis traité comme un
    ...                tag complet, donc jamais préfixé par `ui5-`.
    ${count}=    Get Wc Match Count    tag=ShellBar
    Should Be Equal As Integers    ${count}    2    # <ui5-shellbar-x1b2> + <ui5-shellbar-item-x1b2> : la correspondance par PRÉFIXE inclut les sous-composants de la famille (preuve de présence, jamais cardinalité)
    ${count}=    Get Wc Match Count    tag=SideNavigation
    Should Be Equal As Integers    ${count}    1    # <ui5-side-navigation>, orthographe à tirets
    ${count}=    Get Wc Match Count    tag=ui5-side-navigation
    Should Be Equal As Integers    ${count}    1    # le tag complet reste une demande explicite
    Wc Control Should Be Visible    tag=ShellBar

Short Tag Matches The Mixed Spelling Of A Compound Component
    [Documentation]    La forme MIXTE relevée live sur une barre shell Work Zone
    ...                (2026-08-26) : famille COLLÉE + composant à TIRET
    ...                (`ui5-shellbar-item`). `tag=ShellBarItem` ne matchait
    ...                RIEN avant le correctif : seules les deux formes
    ...                extrêmes (`ui5-shellbaritem`, `ui5-shell-bar-item`)
    ...                étaient essayées ; toutes les combinaisons collé/tiret
    ...                entre les mots le sont désormais.
    ${count}=    Get Wc Match Count    tag=ShellBarItem
    Should Be Equal As Integers    ${count}    1    # <ui5-shellbar-item-x1b2>
    Wc Control Should Be Visible    tag=ShellBarItem
    # le voisin déjà couvert continue de fonctionner : non-régression des formes extrêmes
    ${count}=    Get Wc Match Count    tag=UserMenuItem
    Should Be Equal As Integers    ${count}    0    # absent de la fixture : le zéro reste honnête

Attributes And Text Are Matchable Properties
    [Documentation]    Le matching `properties=` porte sur les attributs de l'hôte
    ...                (mêmes règles que le moteur role : sous-chaîne insensible à la casse).
    Wc Control Should Be Visible    tag=Button    properties={'design': 'Emphasized'}
    Wc Control Should Be Visible    tag=Input    properties={'placeholder': 'name'}
    ${count}=    Get Wc Match Count    tag=Button    text=save
    Should Be Equal As Integers    ${count}    3    # Save + Scoped save + Deep save (insensible à la casse, profond)

Accessible Name Addresses Hosts By User Intent
    [Documentation]    Le cran accessibilité du moteur wc : `name=` matche le NOM
    ...                ACCESSIBLE de l'hôte, la convention UI5 Web Components
    ...                `accessible-name` (attribut) puis `accessibleName`
    ...                (propriété JS non reflétée), puis le texte visible. Le
    ...                localisateur suit l'intention utilisateur, pas la structure.
    Wc Control Should Be Visible    tag=Input    name=Customer name
    ${count}=    Get Wc Match Count    tag=Button    name=Cancel order
    Should Be Equal As Integers    ${count}    1
    # sans attribut ni propriété : le texte visible reste le nom accessible
    Wc Control Should Be Visible    tag=Button    name=Scoped save

Click Wc Control Reaches The Shadow Internals
    [Documentation]    Le clic sur l'hôte résolu atteint le <button> interne au shadow
    ...                root (compteur de la fixture incrémenté).
    Click Wc Control    tag=Button    text=Save    properties={'design': 'Emphasized'}
    ${clicks}=    Evaluate JavaScript    ${None}    () => document.getElementById('clicks').textContent
    Should Be Equal As Integers    ${clicks}    1

Fill Wc Input Pierces The Open Shadow Root
    [Documentation]    La saisie descend jusqu'à l'<input> réel du shadow root ouvert.
    Fill Wc Input    Jean Dupont    tag=Input
    ${value}=    Evaluate JavaScript    ${None}
    ...    () => document.querySelector('ui5-input').shadowRoot.querySelector('input').value
    Should Be Equal    ${value}    Jean Dupont

Fallback Chain Heals Role To Wc On A Registry-Less Page
    [Documentation]    Sur une page sans runtime UI5, le sélecteur role ne résout pas ;
    ...                la chaîne `Resolve Ui5 With Fallback` doit se replier sur `wc=`
    ...                (réparation journalisée en WARNING, jamais silencieuse).
    ${sel}=    Resolve Ui5 With Fallback
    ...    controlType=Button    properties={'text': 'Save'}
    ...    wc={'tag': 'Button', 'text': 'Save'}
    ...    attempt_timeout=2s
    Should Contain    ${sel}    css=
    Click    ${sel}
    ${clicks}=    Evaluate JavaScript    ${None}    () => document.getElementById('clicks').textContent
    Should Be Equal As Integers    ${clicks}    2

Deep Scan Reaches And Clicks A Host Nested In A Shadow Root
    [Documentation]    Un shell Work Zone imbrique des ui5-button DANS le shadow
    ...                root d'autres hôtes (6 en light DOM, 16 en profondeur
    ...                mesurés live le 2026-08-26 : le moteur en voyait 0). Le
    ...                bouton profond de la fixture est SANS id : son chemin
    ...                joint l'hôte et l'intérieur par combinateur DESCENDANT à
    ...                la frontière, et le clic dessus doit agir réellement
    ...                (compteur incrémenté : après les deux clics des tests
    ...                précédents, 3).
    Wc Control Should Be Visible    tag=Button    text=Deep save
    Click Wc Control    tag=Button    text=Deep save
    ${clicks}=    Evaluate JavaScript    ${None}    () => document.getElementById('clicks').textContent
    Should Be Equal As Integers    ${clicks}    3

The Dom Engine Pierces A Shadow Boundary Like Browser Does
    [Documentation]    Le défaut mesuré live le 2026-08-26 : le MÊME sélecteur
    ...                CSS donnait 1 correspondance via la bibliothèque Browser
    ...                (dont le CSS perce les shadow roots ouverts) et 0 via le
    ...                moteur dom. La cause était `matches()`, qui évalue les
    ...                ancêtres dans l'ARBRE de l'élément : un chemin qui
    ...                FRANCHIT une frontière, la forme même que rend le moteur
    ...                wc, ne peut pas y matcher. Le repli perçant le rattrape.
    ...                Le test compare les deux canaux au lieu de graver un
    ...                nombre : c'est la parité qui est la propriété.
    ${chemin}=    Resolve Wc Control    tag=Button    text=Deep save
    # `Resolve Wc Control` rend un sélecteur Browser (préfixe `css=`) ; le
    # moteur dom attend le CSS nu : on retire le préfixe, on ne le redouble pas.
    ${brut}=    Evaluate    $chemin[4:]
    # Témoin du franchissement : l'ancre est l'id de l'hôte, puis un
    # combinateur DESCENDANT (l'espace) vers l'intérieur de son shadow root.
    # C'est cette forme que `matches()` ne peut pas reconnaître.
    ${franchit}=    Evaluate    '[id="deepBar"] ' in $brut
    Should Be True    ${franchit}    msg=Le chemin résolu ne franchit pas la frontière shadow : ${brut}
    ${par_browser}=    Get Element Count    ${chemin}
    ${par_dom}=    Get Dom Match Count    css=${brut}
    Should Be Equal As Integers    ${par_browser}    1
    Should Be Equal As Integers    ${par_dom}    ${par_browser}
    # non-régression : un sélecteur de light DOM garde son résultat exact
    ${light}=    Get Dom Match Count    css=[id="saveBtn"]
    Should Be Equal As Integers    ${light}    1

Open Wc Popups Are Listed And Closed Ones Are Not
    [Documentation]    Le pendant WC de la leçon « un dialogue fermé reste
    ...                rendu » : les DEUX popovers de la fixture sont rendus,
    ...                seul celui qui porte `open` doit sortir de
    ...                `Get Ui5 Open Popups` (mesuré live 2026-08-26 : menu
    ...                utilisateur Work Zone ouvert, keyword aveugle, []).
    ...                Page sans runtime UI5 : les entrées viennent du seul
    ...                balayage WC, `technology=wc`.
    ${popups}=    Get Ui5 Open Popups
    Length Should Be    ${popups}    1
    Should Be Equal    ${popups}[0][id]    openPopover
    Should Be Equal    ${popups}[0][kind]    popover
    Should Be Equal    ${popups}[0][technology]    wc

The Composition Counts Hosts In Depth And In Light Dom
    [Documentation]    `wc_hosts` compte désormais en PROFONDEUR (shadow roots
    ...                ouverts compris) et `wc_hosts_light` garde la mesure de
    ...                surface : l'écart entre les deux dit qu'un shell
    ...                imbrique ses composants (16 contre 6 mesurés live).
    ${comp}=    Get Page Composition
    Should Be True    ${comp}[wc_hosts] > ${comp}[wc_hosts_light]
    Should Be True    ${comp}[wc_hosts_light] >= 8    # les hôtes du light DOM de la fixture

Web Recorder Captures Wc Hosts On A Registry-Less Page
    [Documentation]    Le recorder web, injecté sur une page pur WC, doit transcrire un
    ...                clic en `Click Wc Control` (et Alt+clic en assertion WC) au lieu
    ...                de l'ignorer faute de contrôle UI5/SID.
    ${recjs}=    Normalize Path    ${CURDIR}/../../tools/recorder_web/extension/recorder.js
    ${src}=    Get File    ${recjs}
    Evaluate JavaScript    ${None}    (s) => { (0,eval)(s); }    arg=${src}
    Wait For Function    () => !!document.getElementById('__ui5SpyPanel')    timeout=10s
    Evaluate JavaScript    ${None}
    ...    () => { const p=document.getElementById('__ui5SpyPanel'); [...p.querySelectorAll('button')].find(x=>x.textContent==='rec').click(); }
    Evaluate JavaScript    ${None}
    ...    () => { document.querySelector('[id="saveBtn"]').dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true})); }
    Evaluate JavaScript    ${None}
    ...    () => { document.querySelector('ui5-button-x1b2').dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,altKey:true})); }
    ${panel}=    Evaluate JavaScript    ${None}    () => document.getElementById('__ui5SpyPanel').innerText
    Should Contain    ${panel}    Click Wc Control
    Should Contain    ${panel}    tag=ui5-button
    Should Contain    ${panel}    Wc Control Should Be Visible
    Evaluate JavaScript    ${None}    () => window.__ui5SpyStop()


*** Keywords ***
Open Wc Fixture
    ${fixture}=    Normalize Path    ${CURDIR}/fixtures/wc_fixture.html
    ${url}=    Evaluate    pathlib.Path(r"${fixture}").as_uri()    pathlib
    New Browser    chromium    headless=${HEADLESS}
    New Page    ${url}
    Wait For Function    () => window.__fixtureReady === true    timeout=20s
