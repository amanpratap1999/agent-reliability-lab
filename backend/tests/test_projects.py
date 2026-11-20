def test_project_crud_and_archive(client):
    created = client.post("/api/v1/projects", json={"name": "Reliability evaluation", "description": "First project"})
    assert created.status_code == 201
    project = created.json()
    project_id = project["id"]
    assert project["name"] == "Reliability evaluation"
    assert project["is_archived"] is False
    listed = client.get("/api/v1/projects")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [project_id]
    updated = client.patch(f"/api/v1/projects/{project_id}", json={"name": "Updated project", "description": "Updated description"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated project"
    fetched = client.get(f"/api/v1/projects/{project_id}")
    assert fetched.status_code == 200
    assert fetched.json()["description"] == "Updated description"
    archived = client.post(f"/api/v1/projects/{project_id}/archive")
    assert archived.status_code == 200
    assert archived.json()["is_archived"] is True
    assert client.get("/api/v1/projects").json() == []
    assert len(client.get("/api/v1/projects?include_archived=true").json()) == 1

def test_validation_and_missing_project(client):
    assert client.post("/api/v1/projects", json={"name": "   "}).status_code == 422
    assert client.get("/api/v1/projects/not-a-real-id").status_code == 404
