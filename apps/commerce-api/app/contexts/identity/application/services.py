from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext
from app.contexts.identity.domain.entities import User, UserStatus, AuthProvider
import uuid

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class IdentityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(
        self,
        email: str,
        password: str | None = None,
        auth_provider: AuthProvider = AuthProvider.PASSWORD,
        tenant_id: uuid.UUID | None = None,
    ) -> User:
        """Create a new user account."""
        # Check if email already exists
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise ValueError("Email already registered")
        
        password_hash = None
        if password and auth_provider == AuthProvider.PASSWORD:
            password_hash = pwd_context.hash(password)
        
        user = User(
            id=uuid.uuid4(),
            email=email,
            password_hash=password_hash,
            auth_provider=auth_provider,
            status=UserStatus.GUEST,
            tenant_id=tenant_id,
        )
        
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        
        return user

    async def verify_password(self, user: User, password: str) -> bool:
        """Verify a user's password."""
        if not user.password_hash:
            return False
        return pwd_context.verify(password, user.password_hash)

    async def get_user_by_email(self, email: str) -> User | None:
        """Get a user by email address."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        """Get a user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()