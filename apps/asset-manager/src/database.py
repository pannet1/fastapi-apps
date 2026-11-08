# path: database.py
from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DATABASE_URL = "sqlite:///data/business.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Batch(Base):
    __tablename__ = "batches"
    id = Column(Integer, primary_key=True, autoincrement=True)
    description = Column(String)
    supplier_name = Column(String)
    date = Column(Date)
    items = relationship("Inventory", back_populates="batch")


class Inventory(Base):
    __tablename__ = "inventory"
    inventory_id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"))
    brand = Column(String)
    model = Column(String)
    serial = Column(String, unique=True)
    description_for_ecommerce = Column(String, nullable=True)
    purchase_price = Column(Float)
    total_expenses = Column(Float, default=0.0)
    intended_profit = Column(String)
    selling_price = Column(Float, nullable=True)
    status = Column(String, default="In-Stock")

    # Links item to a specific sale
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=True)
    batch = relationship("Batch", back_populates="items")
    sale_record = relationship("Sale", back_populates="items")


class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    sales = relationship("Sale", back_populates="customer")


class Sale(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    sale_date = Column(Date)
    total_amount = Column(Float)
    amount_paid = Column(
        Float, default=0.0
    )  # Keeps current total for quick dashboard math

    customer = relationship("Customer", back_populates="sales")
    items = relationship("Inventory", back_populates="sale_record")
    # New relationship to track every installment
    payments = relationship("PaymentLog", back_populates="sale")


class PaymentLog(Base):
    __tablename__ = "payment_logs"
    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"))
    amount_received = Column(Float)
    payment_date = Column(Date)
    note = Column(String, nullable=True)  # e.g., "GPay", "Cash", "Cheque"

    sale = relationship("Sale", back_populates="payments")


class Asset(Base):
    __tablename__ = "assets"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    cost = Column(Float)
    purchase_date = Column(Date)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
