from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_breadwinner_field_actions_and_campaign_performance():
    # 1. Create a field action linked to an active campaign
    resp1 = client.post(
        "/breadwinner/api/actions",
        json={
            "task": "Test Campaign Visit",
            "action": "Pitch switchboard demo to Mr. Stephan",
            "time": "14:00",
            "campaign_slug": "stephan_switchboard_retrofit"
        }
    )
    assert resp1.status_code == 200
    action1_data = resp1.json()
    action1_id = action1_data["action_id"]
    assert action1_data["campaign_slug"] == "stephan_switchboard_retrofit"

    # 2. Create an independent field action (no campaign)
    resp2 = client.post(
        "/breadwinner/api/actions",
        json={
            "task": "Personal Laptop Diagnostics",
            "action": "Clean motherboard fan and repaste thermal gel",
            "time": "16:00",
            "campaign_slug": None
        }
    )
    assert resp2.status_code == 200
    action2_data = resp2.json()
    action2_id = action2_data["action_id"]
    assert action2_data["campaign_slug"] is None

    try:
        # 3. Query filtered actions
        all_actions = client.get("/breadwinner/api/actions").json()["actions"]
        assert any(a["id"] == action1_id for a in all_actions)
        assert any(a["id"] == action2_id for a in all_actions)

        # Filter by campaign
        camp_actions = client.get("/breadwinner/api/actions?campaign_slug=stephan_switchboard_retrofit").json()["actions"]
        assert any(a["id"] == action1_id for a in camp_actions)
        assert not any(a["id"] == action2_id for a in camp_actions)

        # Filter by independent
        ind_actions = client.get("/breadwinner/api/actions?campaign_slug=independent").json()["actions"]
        assert any(a["id"] == action2_id for a in ind_actions)
        assert not any(a["id"] == action1_id for a in ind_actions)

        # 4. Check campaign performance endpoint
        perf_resp = client.get("/breadwinner/api/campaigns/stephan_switchboard_retrofit/performance")
        assert perf_resp.status_code == 200
        perf_data = perf_resp.json()
        assert perf_data["campaign"]["slug"] == "stephan_switchboard_retrofit"
        assert "metrics" in perf_data
        assert perf_data["metrics"]["total_actions"] >= 1
        assert any(a["id"] == action1_id for a in perf_data["actions"])

        # Mark action1 as done and check performance recalculation
        client.put(f"/breadwinner/api/actions/{action1_id}", json={"status": "done"})
        perf_resp2 = client.get("/breadwinner/api/campaigns/stephan_switchboard_retrofit/performance")
        perf_data2 = perf_resp2.json()
        assert perf_data2["metrics"]["completed_actions"] >= 1

        # 5. Check all campaigns performance summary endpoint
        all_perf_resp = client.get("/breadwinner/api/campaigns/performance")
        assert all_perf_resp.status_code == 200
        all_perf_data = all_perf_resp.json()
        assert "campaigns_performance" in all_perf_data
        assert "independent_actions" in all_perf_data
        assert all_perf_data["independent_actions"]["total"] >= 1

        # 6. Verify breadwinner dashboard HTML renders with grouped campaign relation
        dash_resp = client.get("/breadwinner/")
        assert dash_resp.status_code == 200
        assert "Campaigns" in dash_resp.text
        assert "Campaign Progress" in dash_resp.text
        assert "Independent" in dash_resp.text
        assert 'data-campaign-group="stephan_switchboard_retrofit"' in dash_resp.text
        assert 'data-campaign-group="independent"' in dash_resp.text
        assert "Scheduled Campaign Field Actions" in dash_resp.text
        assert "Independent Field Actions" in dash_resp.text

    finally:
        # Clean up test actions
        client.delete(f"/breadwinner/api/actions/{action1_id}")
        client.delete(f"/breadwinner/api/actions/{action2_id}")
