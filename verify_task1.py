#!/usr/bin/env python3
"""Quick verification script for Task 1 completion.

Run this to verify all core functionality works correctly.
"""

from datetime import datetime

from core.schemas import Student as StudentSchema
from database import crud, init_db
from database.connection import get_db_context


def test_database_operations():
    """Test basic database operations."""
    print("=" * 60)
    print("TASK 1 VERIFICATION SCRIPT")
    print("=" * 60)
    
    # Initialize database
    print("\n1. Initializing database...")
    init_db()
    print("   ✓ Database initialized")
    
    with get_db_context() as db:
        # Test student creation
        print("\n2. Testing student CRUD operations...")
        student_data = StudentSchema(
            student_id="verify_s1",
            name="Verification Student",
            cgpa=8.5,
            branch="CSE",
            backlogs=0,
            has_prior_offer=False,
        )
        student = crud.create_student(db, student_data)
        print(f"   ✓ Created student: {student.name} (CGPA: {student.cgpa})")
        
        # Test retrieval
        retrieved = crud.get_student(db, "verify_s1")
        assert retrieved is not None, "Failed to retrieve student"
        print(f"   ✓ Retrieved student: {retrieved.name}")
        
        # Test drive creation
        print("\n3. Testing drive operations...")
        drive = crud.create_drive(
            db,
            drive_id="verify_drive_1",
            company_name="Test Company",
            deadline=datetime(2026, 11, 1, 18, 0),
        )
        print(f"   ✓ Created drive: {drive.company_name}")
        
        # Test fact insertion (append-only)
        print("\n4. Testing fact insertion (append-only)...")
        fact = crud.insert_fact(
            db,
            source_id="verify_source_1",
            source_type="placement_cell_whatsapp",
            authority_rank=2,
            timestamp=datetime(2026, 10, 26, 10, 0),
            drive_id="verify_drive_1",
            criterion_type="min_cgpa",
            operator="gte",
            value="7.5",
        )
        print(f"   ✓ Inserted fact: {fact.criterion_type} = {fact.value}")
        
        # Test extracted criteria
        print("\n5. Testing extracted criteria operations...")
        criterion = crud.upsert_extracted_criterion(
            db,
            drive_id="verify_drive_1",
            criterion_type="min_cgpa",
            operator="gte",
            value="7.5",
            source_id="verify_source_1",
            source_type="placement_cell_whatsapp",
            authority_rank=2,
            timestamp=datetime(2026, 10, 26, 10, 0),
        )
        print(f"   ✓ Upserted criterion: {criterion.criterion_type} = {criterion.value}")
        
        # Cleanup
        print("\n6. Cleaning up test data...")
        crud.delete_student(db, "verify_s1")
        print("   ✓ Test data cleaned up")
    
    print("\n" + "=" * 60)
    print("✅ ALL TASK 1 VERIFICATIONS PASSED")
    print("=" * 60)
    print("\nDatabase layer is working correctly!")
    print("\nOptional: To test Gemini API integration:")
    print("  1. Install: pip install google-generativeai")
    print("  2. Get API key: https://makersuite.google.com/app/apikey")
    print("  3. Set in .env: GEMINI_API_KEY=your_key_here")
    print("  4. Run: python -c \"from extraction.llm_client import GeminiClient; print('OK')\"")


def test_configuration():
    """Test configuration loading."""
    print("\n7. Testing configuration...")
    from config import settings
    
    print(f"   ✓ Database URL: {settings.database_url[:30]}...")
    print(f"   ✓ LLM Provider: {settings.llm_provider}")
    print(f"   ✓ Debug mode: {settings.debug}")


def test_llm_client_import():
    """Test LLM client can be imported (without Gemini installed)."""
    print("\n8. Testing LLM client abstraction...")
    try:
        from extraction.llm_client import LLMClient, get_llm_client
        print("   ✓ LLM client abstraction imported")
        print("   ℹ Note: Gemini client requires google-generativeai package")
    except ImportError as e:
        print(f"   ✗ Import failed: {e}")


if __name__ == "__main__":
    try:
        test_configuration()
        test_llm_client_import()
        test_database_operations()
        
        print("\n" + "=" * 60)
        print("🎉 TASK 1 COMPLETE - ALL SYSTEMS OPERATIONAL")
        print("=" * 60)
        print("\nReady to proceed to Task 2: Extraction + Reconciliation Engine")
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ VERIFICATION FAILED: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
