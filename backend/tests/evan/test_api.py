from uuid import uuid4
import pytest
from psycopg import errors
from psycopg.types.json import Jsonb

CONFIG = {
    "name": "Maya",
    "tools": ["phone", "email", "calendar", "payments"],
}


def create(client):
    response = client.post("/agents", json=CONFIG)
    assert response.status_code == 201, response.text
    return response.json()


def seed_task(database, agent_id, status="done"):
    task_id = str(uuid4())
    with database[1]() as conn:
        conn.execute(
            "INSERT INTO tasks (id,agent_id,goal,status,summary) VALUES (%s,%s,%s,%s,%s)",
            (task_id, agent_id, "Book dinner", status, "Confirmed"),
        )
    return task_id


def test_agent_crud_validation_and_archive(client, database):
    agent = create(client)
    assert set(agent) == {"id", "name", "tools"}
    assert client.get("/agents").json() == [agent]
    assert client.get("/agents/" + agent["id"]).json() == agent
    response = client.patch(
        "/agents/" + agent["id"],
        json={"name": "Maya edited", "tools": ["calendar", "calendar"]},
    )
    assert response.json()["tools"] == ["calendar"]
    assert (
        client.patch("/agents/" + agent["id"], json={"name": "  "}).status_code == 422
    )
    assert (
        client.patch("/agents/" + agent["id"], json={"tools": None}).status_code == 422
    )
    assert (
        client.patch(
            "/agents/" + agent["id"], json={"user_id": str(uuid4())}
        ).status_code
        == 422
    )
    task = seed_task(database, agent["id"])
    assert client.delete("/agents/" + agent["id"]).status_code == 204
    assert client.get("/agents").json() == []
    assert client.get("/agents/" + agent["id"]).status_code == 404
    assert client.get("/agents/" + agent["id"] + "/tasks").json()[0]["id"] == task
    with database[1]() as conn:
        with pytest.raises(errors.CheckViolation):
            conn.execute(
                "INSERT INTO tasks (id,agent_id,goal,status) VALUES (%s,%s,%s,%s)",
                (uuid4(), agent["id"], "New task", "planning"),
            )


@pytest.mark.parametrize("status", ["planning", "calling", "awaiting_approval"])
def test_cannot_archive_active_agent(client, database, status):
    agent = create(client)
    seed_task(database, agent["id"], status)
    assert client.delete("/agents/" + agent["id"]).status_code == 409
    assert len(client.get("/agents").json()) == 1


def test_joined_task_shape_and_server_history(client, database):
    agent = create(client)
    task = seed_task(database, agent["id"])
    call, older = str(uuid4()), str(uuid4())
    with database[1]() as conn:
        conn.execute(
            "INSERT INTO calls (id,task_id,to_number,status,started_at,transcript) VALUES (%s,%s,'+440000000000','ended','2026-10-24T10:00Z',%s)",
            (older, task, Jsonb([])),
        )
        conn.execute(
            "INSERT INTO calls (id,task_id,to_number,status,started_at,transcript) VALUES (%s,%s,'+440000000000','ended','2026-10-24T11:00Z',%s)",
            (call, task, Jsonb([{"speaker": "Restaurant", "text": "Confirmed"}])),
        )
        conn.execute(
            "INSERT INTO payments (id,task_id,amount,currency,merchant,status,stripe_pi_id) VALUES (%s,%s,2000,'GBP','The Ivy','paid','secret-provider-id')",
            (uuid4(), task),
        )
        conn.execute(
            "INSERT INTO call_events (ts,call_id,kind,payload) VALUES ('2026-10-24T11:00Z',%s,'answered','{}')",
            (call,),
        )
    [value] = client.get("/agents/" + agent["id"] + "/tasks").json()
    assert value["call"]["id"] == call
    assert value["call"]["transcript"][0]["text"] == "Confirmed"
    assert value["payment"]["amount"] == 2000
    assert "stripe_pi_id" not in value["payment"]
    assert value["events"][0]["call_id"] == call
    assert "calendar_event" not in value
    assert client.get("/agents/" + str(uuid4()) + "/tasks").status_code == 404
    assert client.get("/agents/not-a-uuid/tasks").status_code == 422


def test_empty_history_and_openapi(client):
    agent = create(client)
    assert client.get("/agents/" + agent["id"] + "/tasks").json() == []
    schema = client.get("/openapi.json").json()
    assert "/agents/{agent_id}/tasks" in schema["paths"]
    assert (
        schema["components"]["schemas"]["Payment"]["properties"]["amount"]["type"]
        == "integer"
    )


def test_chat_integration_respects_active_and_archived_agents(client, monkeypatch):
    started = []

    async def run_task(task_id):
        started.append(task_id)

    # Test the actual chat/store SQL without calling Gemini or any provider.
    monkeypatch.setattr("app.routers.chat.run_task", run_task)
    agent = create(client)
    path = "/agents/" + agent["id"]
    response = client.post(path + "/chat", json={"message": "Book dinner"})
    assert response.status_code == 202
    task_id = response.json()["task_id"]
    assert started == [task_id]
    assert client.get(path + "/tasks").json()[0]["status"] == "planning"
    assert client.post(path + "/chat", json={"message": "Again"}).status_code == 409
    assert client.delete(path).status_code == 409

    archived = create(client)
    archived_path = "/agents/" + archived["id"]
    assert client.delete(archived_path).status_code == 204
    assert (
        client.post(
            archived_path + "/chat", json={"message": "Book dinner"}
        ).status_code
        == 404
    )
    assert started == [task_id]


def test_archive_lock_prevents_racing_task_insertion(client, database):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    agent = create(client)
    started = Event()

    def insert():
        with database[1]() as conn:
            started.set()
            try:
                conn.execute(
                    "INSERT INTO tasks (id,agent_id,goal,status) VALUES (%s,%s,%s,%s)",
                    (uuid4(), agent["id"], "Racing request", "planning"),
                )
            except errors.CheckViolation:
                return "blocked"
        return "inserted"

    with database[1]() as conn:
        conn.execute("SELECT id FROM agents WHERE id = %s FOR UPDATE", (agent["id"],))
        conn.execute(
            "UPDATE agents SET archived_at = now() WHERE id = %s", (agent["id"],)
        )
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(insert)
            assert started.wait(2)
            conn.commit()
            assert future.result(timeout=5) == "blocked"


def test_smoke_app_without_database_is_explicitly_unready():
    from fastapi.testclient import TestClient
    from app.evan.app import create_app
    from app.evan.settings import EvanSettings

    with TestClient(
        create_app(
            EvanSettings(
                database_url="", resend_api_key="", email_from="", _env_file=None
            )
        )
    ) as client:
        assert client.get("/health").json()["db"] == "not_configured"
        assert client.get("/agents").status_code == 503
