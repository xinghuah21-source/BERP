import asyncio
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import AsyncSessionLocal
from app.models import Task
from app.models import User
from app.auth import get_password_hash

async def seed():
    async with AsyncSessionLocal() as session:
        existing_user = await session.execute(select(User).where(User.username == "test"))
        user = existing_user.scalar_one_or_none()
        if user is None:
            session.add(
                User(
                    username="test",
                    hashed_password=get_password_hash("123"),
                    role="student",
                    grade=1,
                )
            )
            await session.commit()

        existing = await session.execute(select(func.count()).select_from(Task))
        count = int(existing.scalar() or 0)
        if count > 0:
            print("Success: tasks already seeded")
            return

        tasks = [
            Task(
                id=uuid.uuid4(),
                title="咏鹅",
                content="鹅，鹅，鹅，曲项向天歌。白毛浮绿水，红掌拨清波。",
                content_type="poetry",
                difficulty="easy",
                grade_level=1
            ),
            Task(
                id=uuid.uuid4(),
                title="春晓",
                content="春眠不觉晓，处处闻啼鸟。夜来风雨声，花落知多少。",
                content_type="poetry",
                difficulty="easy",
                grade_level=1
            ),
            Task(
                id=uuid.uuid4(),
                title="静夜思",
                content="床前明月光，疑是地上霜。举头望明月，低头思故乡。",
                content_type="poetry",
                difficulty="easy",
                grade_level=1
            ),
            Task(
                id=uuid.uuid4(),
                title="望庐山瀑布",
                content="日照香炉生紫烟，遥看瀑布挂前川。飞流直下三千尺，疑是银河落九天。",
                content_type="poetry",
                difficulty="medium",
                grade_level=2
            ),
            Task(
                id=uuid.uuid4(),
                title="登鹳雀楼",
                content="白日依山尽，黄河入海流。欲穷千里目，更上一层楼。",
                content_type="poetry",
                difficulty="easy",
                grade_level=1
            ),
        ]
        session.add_all(tasks)
        await session.commit()
        print("Success: 5 tasks seeded")

if __name__ == "__main__":
    import sys
    import selectors
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(seed())
