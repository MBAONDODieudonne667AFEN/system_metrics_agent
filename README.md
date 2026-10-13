# system_metrics_agent - DevSecOps

Agent Python qui collecte des metriques systeme et les envoie a une API FastAPI. Le mode d'emploi d'origine du projet est conserve dans `docs/USAGE.md`.

## Architecture

Fork -> Dockerfiles (api, agent) -> Docker Compose local -> GitHub Actions (tests + SonarQube -> build -> Trivy -> push Docker Hub).

## Choix techniques

- Image de base `python:3.12.15-slim-bookworm` (tag precis, jamais latest) : legere et compatible avec psutil, contrairement a alpine (musl).
- Build multi-stage : pas de cache pip dans l'image finale. `requirements.txt` est copie avant le code pour reutiliser le cache de couches.
- Utilisateur non-root (`app`), aucun secret dans l'image, `.env` exclu par `.dockerignore`.
- uvicorn sans `--reload`, avec `--host 0.0.0.0`. HEALTHCHECK en Python (pas de curl dans slim).
- Paquet `procps` ajoute a l'image de l'agent : il fournit la commande `uptime`.

## Tailles d'images

| Image | Taille sur disque | Taille compressee |
| --- | --- | --- |
| metrics-api | 295 MB | 69,2 MB |
| metrics-agent | 297 MB | 69,6 MB |

## Pipeline

- Job `test` : pytest avec couverture, analyse SonarQube, Quality Gate.
- Job `build-scan-push` (needs: test) : build sans push, scan Trivy (HIGH/CRITICAL corrigeables) avec l'image officielle `aquasec/trivy`, puis push (tags SHA + latest) uniquement sur `main`.
- Images publiees : `mbaondo/system-metrics-api` et `mbaondo/system-metrics-agent`.
- Secrets : `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`, `SONAR_TOKEN`, `SONAR_HOST_URL` (jamais dans le depot).
- PR : https://github.com/MBAONDODieudonne667AFEN/system_metrics_agent/pull/1 (mergee sans squash).
- Run vert sur main : https://github.com/MBAONDODieudonne667AFEN/system_metrics_agent/actions/runs/38333556293

## Preuve d'echec volontaire

Run rouge : https://github.com/MBAONDODieudonne667AFEN/system_metrics_agent/actions/runs/38342350518

Cause : image de base `python:3.10.0-slim` (ancienne). Trivy a bloque le build, et l'etape Push to Docker Hub a ete sautee alors que sa condition etait remplie. Retour au vert : run sur main ci-dessus. La branche de test n'a pas ete mergee.

## Difficultes rencontrees

- Identifiant Docker Hub (`mbaondo`) different de l'identifiant GitHub : connexion refusee tant que l'identifiant n'etait pas corrige.
- Faute de frappe `httpx2` dans `requirements.txt`, corrigee en `httpx`.
- Deux tests `get_load_average` en echec sous Windows (pas de `uptime`), verts sous Linux dans le pipeline.
- Un workflow existant (Black, flake8) bloquait la PR : formatage du code et ajout d'un `.flake8`.
- Tag de `trivy-action` introuvable : scan lance directement avec l'image `aquasec/trivy`.
- Sonar ne controle pas les branches hors main : desactive sur la branche de test.
- Le job `deploy` (VPS) du workflow `pipeline.yaml` reste rouge sur main : secrets VPS absents, hors perimetre du TP.

## Limites : mesures dans un conteneur

Dans un conteneur, psutil et uptime refletent en grande partie l'hote et non les limites cgroups. Pour surveiller une machine, executer l'agent sur l'hote ou lui donner acces a l'hote (`pid: host`, `/proc` en lecture seule), en acceptant les risques de securite. Sous Kubernetes : DaemonSet et metriques cgroup/cAdvisor.

## Bonus : Prometheus

L'API expose ses metriques au format Prometheus sur `/prometheus` (CPU, memoire, charge systeme, nombre de messages recus). Un service `prometheus` (image `prom/prometheus:v3.5.0`) les collecte toutes les 10 secondes selon `prometheus.yml`. Verification : http://localhost:9090/targets, cible en UP. Un test pytest couvre l'endpoint.
