"""
Unit tests for Contact model.
"""
import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.contact import Contact, Gender
from app.models.job import Job, JobStatus


class TestContactModel:
    """Tests for the Contact model."""

    def test_gender_enum_values(self):
        """Test that Gender enum has expected values."""
        assert Gender.MALE.value == "male"
        assert Gender.FEMALE.value == "female"
        assert Gender.UNKNOWN.value == "unknown"

    def test_gender_is_string_enum(self):
        """Test that Gender values work as strings."""
        assert Gender.MALE == "male"
        assert Gender.FEMALE == "female"

    @pytest.mark.asyncio
    async def test_create_contact(self, db_session: AsyncSession):
        """Test creating a new contact."""
        contact = Contact(
            linkedin_url="https://linkedin.com/in/john-doe",
            name="John Doe"
        )
        db_session.add(contact)
        await db_session.flush()
        await db_session.refresh(contact)

        assert contact.id is not None
        assert contact.linkedin_url == "https://linkedin.com/in/john-doe"
        assert contact.name == "John Doe"
        assert contact.gender == Gender.UNKNOWN
        assert contact.is_connection is False
        assert contact.created_at is not None

    @pytest.mark.asyncio
    async def test_contact_with_full_details(self, db_session: AsyncSession):
        """Test creating a contact with all details."""
        contact = Contact(
            linkedin_url="https://linkedin.com/in/jane-smith",
            name="Jane Smith",
            company="Google",
            position="Senior Engineer",
            gender=Gender.FEMALE,
            is_connection=True
        )
        db_session.add(contact)
        await db_session.flush()
        await db_session.refresh(contact)

        assert contact.name == "Jane Smith"
        assert contact.company == "Google"
        assert contact.position == "Senior Engineer"
        assert contact.gender == Gender.FEMALE
        assert contact.is_connection is True

    @pytest.mark.asyncio
    async def test_contact_default_gender(self, db_session: AsyncSession):
        """Test that contact defaults to UNKNOWN gender."""
        contact = Contact(
            linkedin_url="https://linkedin.com/in/test",
            name="Test User"
        )
        db_session.add(contact)
        await db_session.flush()
        await db_session.refresh(contact)

        assert contact.gender == Gender.UNKNOWN

    @pytest.mark.asyncio
    async def test_contact_with_job_relationship(self, db_session: AsyncSession, sample_job: Job):
        """Test contact linked to a job."""
        contact = Contact(
            linkedin_url="https://linkedin.com/in/related-user",
            name="Related User",
            job_id=sample_job.id
        )
        db_session.add(contact)
        await db_session.flush()
        await db_session.refresh(contact)

        assert contact.job_id == sample_job.id

    @pytest.mark.asyncio
    async def test_contact_message_tracking(self, db_session: AsyncSession):
        """Test contact message sent tracking."""
        contact = Contact(
            linkedin_url="https://linkedin.com/in/messaged-user",
            name="Messaged User",
            message_sent_at=datetime.utcnow(),
            message_content="Hello, I saw your profile!"
        )
        db_session.add(contact)
        await db_session.flush()
        await db_session.refresh(contact)

        assert contact.message_sent_at is not None
        assert contact.message_content == "Hello, I saw your profile!"

    @pytest.mark.asyncio
    async def test_contact_connection_request_tracking(self, db_session: AsyncSession):
        """Test contact connection request tracking."""
        contact = Contact(
            linkedin_url="https://linkedin.com/in/pending-connect",
            name="Pending Connection",
            is_connection=False,
            connection_requested_at=datetime.utcnow()
        )
        db_session.add(contact)
        await db_session.flush()
        await db_session.refresh(contact)

        assert contact.is_connection is False
        assert contact.connection_requested_at is not None

    @pytest.mark.asyncio
    async def test_contact_unique_linkedin_url(self, db_session: AsyncSession):
        """Test that linkedin_url must be unique."""
        contact1 = Contact(
            linkedin_url="https://linkedin.com/in/unique-user",
            name="User One"
        )
        db_session.add(contact1)
        await db_session.flush()

        contact2 = Contact(
            linkedin_url="https://linkedin.com/in/unique-user",  # Same URL
            name="User Two"
        )
        db_session.add(contact2)

        with pytest.raises(Exception):  # IntegrityError
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_contact_repr(self, db_session: AsyncSession):
        """Test contact string representation."""
        contact = Contact(
            linkedin_url="https://linkedin.com/in/repr-test",
            name="Repr Test",
            company="TestCo"
        )
        db_session.add(contact)
        await db_session.flush()
        await db_session.refresh(contact)

        repr_str = repr(contact)
        assert "Contact" in repr_str
        assert "Repr Test" in repr_str
        assert "TestCo" in repr_str

    @pytest.mark.asyncio
    async def test_query_contacts_by_gender(self, db_session: AsyncSession):
        """Test querying contacts by gender."""
        contacts = [
            Contact(linkedin_url="https://linkedin.com/in/m1", name="Male 1", gender=Gender.MALE),
            Contact(linkedin_url="https://linkedin.com/in/f1", name="Female 1", gender=Gender.FEMALE),
            Contact(linkedin_url="https://linkedin.com/in/m2", name="Male 2", gender=Gender.MALE),
        ]
        db_session.add_all(contacts)
        await db_session.flush()

        result = await db_session.execute(
            select(Contact).where(Contact.gender == Gender.MALE)
        )
        male_contacts = result.scalars().all()

        assert len(male_contacts) == 2
        for contact in male_contacts:
            assert contact.gender == Gender.MALE

    @pytest.mark.asyncio
    async def test_query_connections_only(self, db_session: AsyncSession):
        """Test querying only connected contacts."""
        contacts = [
            Contact(linkedin_url="https://linkedin.com/in/c1", name="Connected 1", is_connection=True),
            Contact(linkedin_url="https://linkedin.com/in/c2", name="Not Connected", is_connection=False),
            Contact(linkedin_url="https://linkedin.com/in/c3", name="Connected 2", is_connection=True),
        ]
        db_session.add_all(contacts)
        await db_session.flush()

        result = await db_session.execute(
            select(Contact).where(Contact.is_connection == True)
        )
        connections = result.scalars().all()

        assert len(connections) == 2


class TestGenderEnum:
    """Tests for Gender enum."""

    def test_all_gender_values_exist(self):
        """Verify all expected gender values exist."""
        expected = {"male", "female", "unknown"}
        actual = {g.value for g in Gender}
        assert actual == expected

    def test_gender_from_string(self):
        """Test creating gender from string value."""
        assert Gender("male") == Gender.MALE
        assert Gender("female") == Gender.FEMALE
        assert Gender("unknown") == Gender.UNKNOWN

    def test_invalid_gender_raises(self):
        """Test that invalid gender raises ValueError."""
        with pytest.raises(ValueError):
            Gender("other")
