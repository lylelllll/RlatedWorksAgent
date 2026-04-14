import asyncio
import os
import sys

# Ensure backend package can be found
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.db.database import init_db, AsyncSessionLocal
from backend.db import crud

async def main():
    print("Initializing DB...")
    await init_db()
    print("DB initialized successfully.")

    async with AsyncSessionLocal() as db:
        print("Creating a new project...")
        new_project = await crud.create_project(
            db=db,
            title="Test Project",
            research_direction="Trustworthy AI",
            target_journal="IEEE S&P"
        )
        print(f"Created project: ID={new_project.id}, Title={new_project.title}")

        print("Querying projects...")
        projects = await crud.get_projects(db)
        print(f"Found {len(projects)} project(s).")
        for p in projects:
            print(f"  - {p.id}: {p.title}")

        print("\nAdding conversation...")
        conv = await crud.create_conversation(
            db=db,
            project_id=new_project.id,
            role="user",
            content="Hello world, I want to write a paper."
        )
        print(f"Created conversation: ID={conv.id}, Role={conv.role}, Content={conv.content}")

        print("\nQuerying conversations for project...")
        convs = await crud.get_project_conversations(db, new_project.id)
        print(f"Found {len(convs)} conversation(s).")
        for c in convs:
            print(f"  - {c.role}: {c.content}")
        
    print("\nDatabase test successfully passed!")

if __name__ == "__main__":
    asyncio.run(main())
