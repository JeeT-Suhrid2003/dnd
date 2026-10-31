
# D&D Microservices

Phase 1: everything runs locally as separate processes. Docker and orchestration come next.

| Service   | Port | Job                                                   |
|-----------|------|-------------------------------------------------------|
| gateway   | 8000 | Single entry point, routes to the services below      |
| dice      | 8001 | Rolls dice (`2d6+3`, `4d6kh3`, d20 advantage)          |
| character | 8002 | Character / monster sheets (PostgreSQL)               |
| combat    | 8003 | Initiative and attacks; calls dice + character        |

Services find each other through env vars (`DICE_URL`, `CHARACTER_URL`, `COMBAT_URL`),
defaulting to localhost, so the same code works in Docker later by changing only these.

## Run

    pip install -r requirements.txt
    ./run_local.sh
    pytest tests -q

On Windows PowerShell, start each service in a separate terminal from the project
folder. Start the database first with Docker:

    docker compose up -d db

Then set the database connection details for the character service:

    $env:DB_HOST="localhost"
    $env:DB_PORT="5432"
    $env:DB_NAME="dnd"
    $env:DB_USER="dnd"
    $env:DB_PASSWORD="dnd-dev-password"

    python -m uvicorn main:app --app-dir services\dice --port 8001
    python -m uvicorn main:app --app-dir services\character --port 8002
    python -m uvicorn main:app --app-dir services\combat --port 8003
    python -m uvicorn main:app --app-dir services\gateway --port 8000

Open **http://localhost:8000/** to play in the browser. The game page lets you
create characters, roll animated initiative and attacks, take turns, choose a
target, roll with advantage or disadvantage, defend for +2 AC against the next
attack, and reset the seeded Goblin's HP. Interactive API docs are also available at
http://localhost:8000/docs (or on each service at http://localhost:800X/docs).
Open the game through this address, not by double-clicking
`frontend/index.html`, so its requests can connect to the API.

## Gateway Docker image

Build from the repository root so Docker can copy both the gateway code and
frontend files:

    docker build -f services/gateway/Dockerfile -t dnd-gateway .

The gateway expects the other containers to be reachable by the names `dice`,
`character`, and `combat` on the same Docker network. Its container listens on
port 8000; publish it on an available host port (for example, `-p 8111:8000`
if port 8000 is already in use) and open that host port in your browser. Override
`DICE_URL`, `CHARACTER_URL`, or `COMBAT_URL` if your container names or ports
differ.

## Run with Docker Compose

From the repository root, build and start all services:

    docker compose up --build

Open **http://localhost:8111/**. To use a different host port, set
`GATEWAY_PORT` (for example, `$env:GATEWAY_PORT=8000` in PowerShell) before
starting Compose. PostgreSQL stores character data in the `character_db_data`
named volume, which survives container restarts and `docker compose down`.
Remove the database as well with `docker compose down -v`. Set `POSTGRES_PASSWORD`
before starting Compose to override the development-only default password.

The character-service integration tests use a PostgreSQL database configured by
`TEST_DATABASE_URL`. Point it only at a disposable test database; tests clear its
character and metadata tables.

## Apply Kubernetes Services with Terraform

Terraform applies every Service document in `k8s/service.yml` to the Kubernetes
cluster selected by the current kubeconfig context. Ensure `kubectl` is
configured for the target cluster, then run these commands from the repository
root:

    terraform -chdir=terraform init
    terraform -chdir=terraform plan
    terraform -chdir=terraform apply

To use a kubeconfig at a different path, pass `-var="kubeconfig_path=<path>"`
to both `plan` and `apply`.

The PostgreSQL Deployment uses the `dnd-postgres-data` PersistentVolumeClaim.
Before applying `k8s/deployment.yml`, create the database password Secret:

    kubectl create secret generic dnd-db-credentials --from-literal=password=your-strong-password
    kubectl apply -f k8s/deployment.yml

The character service connects to the in-cluster `dnd-postgres` Service. Do not
commit the database password to the repository.

## Try it (through the gateway)

    curl -X POST localhost:8000/dice/roll -H 'content-type: application/json' -d '{"notation":"4d6kh3"}'
    curl -X POST localhost:8000/dice/d20  -H 'content-type: application/json' -d '{"modifier":5,"advantage":true}'
    curl localhost:8000/characters
    curl -X POST localhost:8000/combat/initiative -H 'content-type: application/json' -d '{"combatant_ids":["aria","goblin"]}'
    curl -X POST localhost:8000/combat/attack -H 'content-type: application/json' -d '{"attacker_id":"aria","target_id":"goblin"}'

Seeded combatants: `aria` (Fighter, AC 16) and `goblin` (AC 15, 7 HP).
Open **Create character** from the game header to add another player or monster.
Characters are stored in PostgreSQL and appear in initiative the next time an encounter starts.
Reset HP with `POST /characters/goblin/reset`.

## Dice notation

`NdM`, optional keep highest/lowest (`kh`/`kl`), optional modifier: `d20`, `2d6+3`, `4d6kh3`, `1d20-1`.
Limits: 1-100 dice, 2-1000 sides. Nat 20 / nat 1 are flagged on single d20 rolls.

# dnd
lets play
