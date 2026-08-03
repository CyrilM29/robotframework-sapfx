> **🇬🇧 English** · [🇫🇷 Français](ecc-validation.fr.md)

# Live ECC Validation — ABAP System (CAL or Docker) + SAP GUI

End-to-end procedure for running `tests/robot/ecc_smoke.robot` against a real
SAP system (A4H system), using the **SAP GUI for Windows** client.

> 🚧 **Docker image availability (2026)**: as of today, the image
> `sapse/abap-cloud-developer-trial` is **not found / 404 on Docker Hub**
> based on multiple community reports — SAP appears to have withdrawn it (at least
> temporarily). The older `sapse/abap-platform-trial` is also withdrawn and
> *AS ABAP 7.xx Developer Edition* is **EOL (May 2026)**.
>
> ➡️ **Recommended path today: SAP Cloud Appliance Library (CAL)** — see
> **§ A**. **§ B (Docker)** remains valid *if/when* the image becomes available
> again on Docker Hub. Once a system is reachable (CAL or Docker), **§ 5 → § 10**
> (SAP GUI connection, scripting, execution) are common to both options.

> Code-level validation is already covered offline by `tests/unit`
> (in particular `test_ecc_flow.py`, simulated COM session). This document covers
> real navigation, which requires a live system.

## 0. Prerequisites (state on this machine)

| Item | Required | This machine |
|---|---|---|
| RAM | 16 GB min (32+ recommended) | **128 GB ✓** |
| Free disk | ~170 GB recommended (image >53 GB uncompressed) | **C: 241 GB ✓** |
| Docker (Linux containers) | yes | **27.5.1 ✓** (Docker Desktop) |
| SAP GUI for Windows | yes | **8.00 64-bit ✓** (`C:\Program Files\SAP\FrontEnd\SAPgui\saplogon.exe`) |
| `pywin32` | yes | **✓** |

> ✅ **Client + scripting check (no server)** — already validated live on this
> machine. Reproducible anytime: `python tests/manual/check_sap_gui_connection.py`.
> It launches SAP Logon, attaches to the scripting engine (COM) and reads the
> `GuiApplication` (here SAP GUI 8.00, scripting active). **Screen manipulation**
> additionally needs a connected session (option A or B).

> The **Docker / RAM / disk** rows in the §0 table apply only to **option B**
> (local container). For **option A (CAL)**, the system runs in the cloud; you
> mainly need the local **SAP GUI** client + `pywin32` (already ✓).

## A. Recommended Option — SAP Cloud Appliance Library (CAL)

Same product (ABAP/ECC Developer Edition), but as a **hosted appliance**: the
SAP software is free, you only pay for **cloud hosting** (AWS/Azure/GCP) while
the instance is running (and you can *suspend* it to reduce costs).

1. A **SAP Universal ID** account (free) + a **hyperscaler** account (AWS/Azure/GCP)
   with billing access.
2. Go to **<https://cal.sap.com/catalog>**, search for an **"ABAP
   Platform Developer Edition"** / **"ABAP Cloud Developer Trial"** solution, accept the
   terms, and **create an instance** (choose region + VM type).
3. CAL provisions the VM and displays the **connection details**: public hostname,
   SID, instance number, and passwords (often `DEVELOPER` / password set at creation,
   instance master password).
4. Open the SAP GUI ports (3200 + 33xx) in the VM firewall / security group,
   or use the access provided by CAL.
5. Continue directly to **§ 5** (SAP GUI connection) — replacing the host
   `vhcala4hci` with the **public hostname of the CAL VM** and the credentials with
   those displayed in CAL.

> Cost tip: **suspend** the instance in CAL as soon as you are not using it — you
> then pay almost only for storage.

## B. Docker Option — Manual Prerequisites (if the image is available)

> Only applies if `sapse/abap-cloud-developer-trial` is once again **present
> on Docker Hub** (see the availability note at the top). Otherwise, use **option A**.

The SAP image is **protected**: a direct `docker pull` returns
`denied: requested access to the resource is denied`. Before anything:

1. **Log in to Docker Hub** (free account):

   ```powershell
   docker login
   ```

2. **Accept the SAP terms** on the image page (logged in with the same
   account): <https://hub.docker.com/r/sapse/abap-cloud-developer-trial> → click
   the provider terms *Accept / Proceed* button. Without this web acceptance, the pull
   remains denied (`denied: requested access to the resource is denied`).

## 2. Pull the Image

Choose the tag from the *Tags* tab on
<https://hub.docker.com/r/sapse/abap-cloud-developer-trial> (⚠️ the *Overview*
page explicitly states **not** to pull from there). Replace `<TAG>` below
with the most recent available tag (e.g. `2022`, `2025`):

```powershell
docker pull sapse/abap-cloud-developer-trial:<TAG>
```

(Image ~23 GB compressed, >53 GB uncompressed; duration depends on bandwidth.)

## 3. Start the Container

> The `-agree-to-sap-license` flag constitutes **acceptance of the SAP developer licence**.
> Unlike the older image, the ABAP Cloud Developer Trial has a **fixed default password
> depending on the version** (no `-master-password`) — see §5.

```powershell
docker run --stop-timeout 3600 -i --name a4h -h vhcala4hci `
  -p 3200:3200 -p 3300:3300 -p 8443:8443 -p 30213:30213 -p 50000:50000 -p 50001:50001 `
  sapse/abap-cloud-developer-trial:<TAG> `
  -agree-to-sap-license -skip-limits-check
```

> Verify the exact command (flags, ports) in the *Tags* tab / the documentation for the
> chosen version, as it may change from one release to another.

The first start-up (HANA + ABAP) takes **10–30 min**. Follow the logs:

```powershell
docker logs -f a4h
```

Wait for the message indicating the system is started ("Instance on host
vhcala4hci started" / end prompt). `Ctrl+C` detaches the log display (does not kill
the container, started with `-i`).

## 4. Name Resolution (hosts)

Add to `C:\Windows\System32\drivers\etc\hosts` (editor as administrator):

```text
127.0.0.1   vhcala4hci
```

## 5. SAP GUI Connection

Open **SAP Logon** → *New* → *Connection to a Custom Application Server*:

| Field | Value |
|---|---|
| Description | `A4H` (must match `SAP_CONNECTION`, see §8) |
| Application Server | **option B (Docker)**: `vhcala4hci` (or `localhost`) — **option A (CAL)**: public hostname of the VM |
| Instance Number | `00` |
| System ID (SID) | `A4H` |

Trial system credentials:

| Client | User | Password (depending on version) | Purpose |
|---|---|---|---|
| `001` | `DEVELOPER` | e.g. `ABAPtr2022#01` (2022), `ABAPtr2023#00` (2023) | development |
| `000` | `SAP*` / `DDIC` | same version default password | admin |

The default password **depends on the tag**: retrieve it from the documentation / the
*Tags* tab of the chosen version. On first login, SAP may prompt you to change it.

## 6. ABAP Licence (if expired)

The trial system includes a temporary licence. If it has expired
(message at login): transaction **`SLICENSE`** → note the *hardware key* →
request a free 90-day licence ("minisap") for the ABAP Platform product
on the SAP portal, then install it in `SLICENSE`.

## 7. Enable SAP GUI Scripting

**Server side** (transaction **`RZ11`**):

- Parameter `sapgui/user_scripting` → value **`TRUE`** (dynamic change).
- To make it persistent after restart: set it in the profile via `RZ10`.
- Optional: `sapgui/user_scripting_disable_recording = FALSE`,
  `sapgui/user_scripting_per_user` as needed.

**Client side** (SAP Logon → *Options* → *Accessibility & Scripting* → *Scripting*):

- Check **Enable scripting**.
- **Uncheck** *Notify when a script attaches to SAP GUI* and *Notify when a script
  opens a connection* (otherwise popups will block automation).

Quick check: the library's `connect to session` command must
find the engine (`GetScriptingEngine`). If it fails with "is Sap Logon Pad
open?", scripting is not active on both sides.

## 8. Run `ecc_smoke.robot`

The suite uses `resources/ecc_keywords.resource`:
`Open Sap Logon` (launches `saplogon.exe`) → `Connect To Session With Retry` →
`Open Connection ${SAP_CONNECTION}` → login input → transactions.

`SAP_CONNECTION` must be **exactly** the *Description* of the SAP Logon entry (§5).

```powershell
robot --pythonpath src `
  -v SAP_CONNECTION:"A4H" `
  -v SAP_USER:DEVELOPER `
  -v "SAP_PASSWORD: Secret:ABAPtr2022#01" `
  -v SAP_CLIENT:001 `
  -v SAP_LANGUAGE:EN `
  tests/robot/ecc_smoke.robot
```

(Adjust `SAP_PASSWORD` to the default password of the chosen version — see §5.
The `: Secret:` form is Robot Framework 7.4's typed-variable syntax: the value
is masked everywhere, even in TRACE logs.)

Results in `output.xml` / `log.html` / `report.html`.

## 9. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `denied` on pull | §B not done: `docker login` + accept terms on the Docker Hub page. |
| `not found` / 404 on pull | The Docker image is currently withdrawn from Docker Hub → use **option A (CAL)**. |
| Popup "A script is opening a connection…" | Uncheck notifications on the client side (§7). |
| `Could not connect to Session, is Sap Logon Pad open?` | `sapgui/user_scripting` not `TRUE` (RZ11) or client scripting disabled. |
| `Cannot open connection 'A4H'` | SAP Logon *Description* ≠ `SAP_CONNECTION`. |
| Login denied / password expired | Change the password at login; verify client `001` / user `DEVELOPER`. |
| Licence message at login | Install a minisap licence via `SLICENSE` (§6). |
| `Logon not possible (error in license check)` (client 001 — GUI *and* OData) | Licence expired/invalid (§6). Meanwhile `SAP*` / client `000` still logs on for admin tasks (§11.7). |
| `SAP Gateway has been deactivated` (OData HTTP 500, `/IWFND/CM_COS/003`) | Re-created container: run IMG activity `/IWFND/IWF_ACTIVATE` as `SAP*`/000 → *Activate* (§11.7). |
| Very long start-up / HANA not ready | Wait for completion in `docker logs -f a4h` before testing. |

## 10. Container Lifecycle

```powershell
docker stop a4h      # clean shutdown (may take time: --stop-timeout 3600)
docker start a4h     # restart (faster than first boot)
docker rm a4h        # delete (system data is lost)
```

## 11. Validated Live — Hard Points Encountered (✅ ecc_smoke 5/5)

Real validation performed with a **1909 image** (the official one being withdrawn:
third-party re-upload `toberic/abap-platform-trial:1909`, ⚠️ unofficial — see
licence/security caveats). These points are **generic** to the ABAP Platform Trial under
Docker Desktop/Windows:

1. **sysctl for HANA (otherwise HANA will not start).** Docker Desktop/WSL2 has limits
   that are too low; `-skip-limits-check` bypasses the *check* but not the *limit*.
   Apply the settings to the VM kernel via a privileged container:

   ```powershell
   docker run --rm --privileged --entrypoint /bin/sh toberic/abap-platform-trial:1909 `
     -c "sysctl -w vm.max_map_count=2147483647 fs.aio-max-nr=18446744073709551615 kernel.shmmni=32768"
   ```

   Then start a4h with `--sysctl kernel.shmmni=32768`.

2. **Two expired licences → minisap (§6/§7), with one key subtlety: hardware keys are
   specific to the container** (derived from the MAC). Read the key **from the a4h
   container itself**:
   - ABAP: `docker exec a4h su - a4hadm -c "saplikey pf=/usr/sap/A4H/SYS/profile/A4H_D00_vhcala4hci -get"`
   - HANA: `M_LICENSE.HARDWARE_KEY` via `hdbsql -i 02 -d SYSTEMDB -u SYSTEM -p <pw>`

   Obtain at <https://go.support.sap.com/minisap> (system **A4H**; HANA =
   *SAP HANA Platform Edition (64GB)*), then install:

   ```powershell
   docker cp ASABAP_license a4h:/opt/sap/ASABAP_license
   docker cp HDB_license    a4h:/opt/sap/HDB_license
   docker exec a4h /usr/local/bin/hdb_license_update
   docker exec a4h /usr/local/bin/asabap_license_update
   docker restart a4h        # clean boot: disp+work GREEN, "Have fun!"
   ```

3. **Server-side scripting (otherwise scripting sees the connection but 0 sessions).**
   Append to the instance profile then restart the instance:

   ```powershell
   docker exec a4h bash -lc "echo 'sapgui/user_scripting = TRUE' >> /usr/sap/A4H/SYS/profile/A4H_D00_vhcala4hci"
   docker exec a4h su - a4hadm -c "sapcontrol -nr 00 -function RestartInstance"
   ```

4. **Name resolution:** `127.0.0.1 vhcala4hci` in the hosts file (as administrator).

5. **Connection without a SAP Logon entry:** connection string `/H/vhcala4hci/S/3200`
   via the **`Open Connection By String`** keyword (`Open Connection` standard requires a
   saved entry). Login **`DEVELOPER` / client `001` / `Htods70334`** — SAP's own
   published default for this trial image, not a real secret; still, prefer
   supplying it via `-v "SAP_PASSWORD: Secret:..."` (the RF 7.4 typed variable,
   masked even in TRACE logs) or an env var rather than hardcoding it in
   scripts, so a secret scanner never has to make that judgment call for you.

6. **Validated execution:**

   ```powershell
   robot --pythonpath src -v SAP_CONNECTION:/H/vhcala4hci/S/3200 `
     -v SAP_USER:DEVELOPER -v "SAP_PASSWORD: Secret:Htods70334" -v SAP_CLIENT:001 `
     tests/robot/ecc_smoke.robot
   ```

   → **5/5 PASS** (login, SE16 navigation, T000 browse, **ALV grid** read SM50,
   unknown transaction).

7. **A re-created container starts bare — and its licences die with the old MAC.**
   `docker rm` + `docker run` resets everything done since the first provisioning:
   the ABAP hardware key derives from eth0's MAC address (pin it with
   `--mac-address` at `docker run`, otherwise the key — and the licence — changes;
   under Docker 29 a container created *without* `--mac-address` even changes MAC
   at every `docker start`), and the scripting profile line (point 3), the ICF
   `webgui` service (SICF) and the **SAP Gateway activation** are all gone.
   Everything below is fixable **without a valid licence**, because `SAP*` in
   client `000` still logs on — only client `001` is blocked by the licence
   check, on the GUI *and* on OData (same "error in license check"):
   - OData answers HTTP 500 `/IWFND/CM_COS/003` *"SAP Gateway has been
     deactivated"* → run the IMG activity **`/IWFND/IWF_ACTIVATE`** ("Activate
     or Deactivate SAP Gateway", SPRO → SAP Gateway → OData Channel →
     Configuration) and click *Activate*. Its generated tcode can be read from
     table `CUS_IMGACH` (`/IWFND/50000003` on the 1909 image); the setting is
     **cross-client** — one pass is enough (verified live 2026-08-02: client 000
     catalogue = 38 services right after).
   - Caveat while doing it: `Run Transaction` on a generated IMG tcode fails as
     a **false negative** — the transaction *did* start, but under its internal
     name (`active='/IWFND/IWF_ACTIVATE'`). Perceive the screen before
     concluding (see `memory/run-transaction-tcodes-parametres.md`).

> Real-world note: on this system, a non-existent transaction returns a status of type
> **`S`** (not `E`) — `Run Transaction` was therefore corrected to compare the
> **active transaction** (`session.Info.Transaction`), the only criterion that is truly
> language-independent.

---

- **Option A (CAL)**: once the instance is created and reachable, provide the
  public hostname + credentials, and I will guide you through §5→§8 (SAP GUI
  connection, scripting, running `ecc_smoke`).
- **Option B (Docker)**: if the image becomes available again, after `docker login` +
  accepting the terms, I will walk through §2→§3 (pull + run) then §4→§8.

## Sources

- SAP Cloud Appliance Library (option A): <https://cal.sap.com/catalog>
- Official image documentation: <https://github.com/SAP-docs/abap-platform-trial-image>
- Docker Hub image (option B, currently 404): <https://hub.docker.com/r/sapse/abap-cloud-developer-trial>
- SAP Community — ABAP Cloud Developer Trial 2023:
  <https://community.sap.com/t5/technology-blog-posts-by-sap/abap-cloud-developer-trial-2023-available-now/ba-p/14057183>
