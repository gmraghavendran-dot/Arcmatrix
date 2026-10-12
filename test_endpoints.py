from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.config import settings
from backend.services.platform_service import PlatformService
from backend.services.engineering_service import EngineeringService
from backend.services.cicd_service import CicdService
from backend.services.cloud_service import CloudService
from backend.services.ai_service import AiService
from backend.services.insight_service import InsightService

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def main():
    db = SessionLocal()
    try:
        print("1. Testing PlatformService...")
        plat_srv = PlatformService()
        p_sum = plat_srv.summary(db)
        assert "engineering" in p_sum, "Missing engineering in platform summary"
        assert "cicd" in p_sum, "Missing cicd in platform summary"
        assert "cloud" in p_sum, "Missing cloud in platform summary"
        assert "ai" in p_sum, "Missing ai in platform summary"
        assert "critical_risks_count" in p_sum, "Missing critical_risks_count"
        assert len(p_sum["provenance"]) == 4, "Provenance should have 4 domains"
        print("   [PASS] Platform summary OK")

        print("2. Testing EngineeringService...")
        eng_srv = EngineeringService()
        e_hlth = eng_srv.health(db)
        assert e_hlth.get("repositories_count", 0) > 0, "No engineering repos"
        e_repos = eng_srv.repositories(db, limit=5)
        assert len(e_repos["items"]) > 0, "No repos in list"
        repo_id = e_repos["items"][0]["repo_id"]
        e_detail = eng_srv.repository_detail(db, repo_id)
        assert e_detail is not None, f"Detail not found for repo {repo_id}"
        print(f"   [PASS] Engineering OK (checked repo {repo_id})")

        print("3. Testing CicdService...")
        cicd_srv = CicdService()
        c_hlth = cicd_srv.health(db)
        assert c_hlth.get("repositories_count", 0) > 0, "No cicd repos"
        c_repos = cicd_srv.repositories(db, limit=5)
        assert len(c_repos["items"]) > 0, "No cicd repos in list"
        repo_name = c_repos["items"][0]["repo"]
        c_detail = cicd_srv.repository_detail(db, repo_name)
        assert c_detail is not None, f"Detail not found for repo {repo_name}"
        print(f"   [PASS] CI/CD OK (checked repo {repo_name})")

        print("4. Testing CloudService...")
        cld_srv = CloudService()
        cld_eff = cld_srv.efficiency(db)
        assert cld_eff.get("total_service_regions", 0) > 0, "No service regions"
        providers = cld_srv.providers(db)
        assert len(providers) > 0, "No providers found"
        services = cld_srv.services(db, limit=5)
        assert len(services["items"]) > 0, "No services in list"
        print(f"   [PASS] Cloud OK ({len(providers)} providers, {len(services['items'])} sample services)")

        print("5. Testing AiService...")
        ai_srv = AiService()
        ai_hlth = ai_srv.health(db)
        assert ai_hlth.get("models_count", 0) > 0, "No AI models found"
        models = ai_srv.models(db, limit=5)
        assert len(models["items"]) > 0, "No models in list"
        model_name = models["items"][0]["model"]
        ai_detail = ai_srv.model_detail(db, model_name)
        assert ai_detail is not None, f"Detail not found for model {model_name}"
        print(f"   [PASS] AI OK (checked model {model_name})")

        print("6. Testing InsightService...")
        ins_srv = InsightService()
        ins_sum = ins_srv.summary(db)
        assert "counts_by_severity" in ins_sum, "Missing severity counts"
        crit = ins_srv.critical(db, limit=10)
        assert len(crit) > 0, "No critical insights found"
        warn = ins_srv.warnings(db, limit=10)
        assert len(warn) > 0, "No warning insights found"
        all_ins = ins_srv.list_insights(db, limit=10)
        assert len(all_ins["items"]) > 0, "No insights listed"
        print(f"   [PASS] Insights OK ({len(crit)} critical, {len(warn)} warnings retrieved)")

        print("\nALL BACKEND SERVICE TESTS PASSED SUCCESSFULLY!")
        return 0
    finally:
        db.close()

if __name__ == "__main__":
    raise SystemExit(main())
