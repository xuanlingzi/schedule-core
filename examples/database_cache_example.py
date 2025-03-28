"""
数据库和缓存使用示例
"""

from sqlalchemy import Column, Integer, String, create_engine
from schedule_core import Base, get_db, cache, logger, core_settings


# 定义一个示例模型
class User(Base):
    """用户模型"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, nullable=False)


def init_db():
    """初始化数据库"""
    # 注意：通常你会在应用启动时执行此操作
    engine = create_engine(core_settings.DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表已创建")


def add_user(name, email):
    """添加用户到数据库并更新缓存"""
    db = next(get_db())
    try:
        # 检查用户是否已存在
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            logger.warning(f"用户 {email} 已存在")
            return existing_user

        # 创建新用户
        user = User(name=name, email=email)
        db.add(user)
        db.commit()
        db.refresh(user)

        # 更新缓存
        cache.set(f"user:{user.id}", user.name)
        cache.set(f"email:{user.id}", user.email)

        logger.info(f"用户 {name} 已添加到数据库，ID: {user.id}")
        return user
    except Exception as e:
        db.rollback()
        logger.error(f"添加用户失败: {str(e)}")
        raise
    finally:
        db.close()


def get_user(user_id):
    """从缓存或数据库获取用户"""
    # 尝试从缓存获取
    cached_name = cache.get(f"user:{user_id}")
    cached_email = cache.get(f"email:{user_id}")

    if cached_name and cached_email:
        logger.info(f"从缓存中获取用户 {user_id}")
        return {"id": user_id, "name": cached_name, "email": cached_email}

    # 如果缓存中没有，从数据库获取
    logger.info(f"缓存未命中，从数据库获取用户 {user_id}")
    db = next(get_db())
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"用户 {user_id} 不存在")
            return None

        # 更新缓存
        cache.set(f"user:{user.id}", user.name)
        cache.set(f"email:{user.id}", user.email)

        return {"id": user.id, "name": user.name, "email": user.email}
    finally:
        db.close()


def main():
    """主函数"""
    # 初始化数据库（确保表存在）
    init_db()

    # 添加用户
    user1 = add_user("张三", "zhangsan@example.com")
    user2 = add_user("李四", "lisi@example.com")

    # 获取用户（第一次从数据库）
    user_info = get_user(user1.id)
    print(f"用户信息: {user_info}")

    # 再次获取（应该从缓存获取）
    user_info = get_user(user1.id)
    print(f"再次获取用户信息: {user_info}")

    # 手动清除缓存
    cache.delete(f"user:{user1.id}")
    cache.delete(f"email:{user1.id}")

    # 清除缓存后再次获取（应该从数据库获取）
    user_info = get_user(user1.id)
    print(f"清除缓存后获取用户信息: {user_info}")


if __name__ == "__main__":
    main()
