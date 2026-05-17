-- Quản lý kho hàng
CREATE TABLE Inventory (
    InventoryID INT PRIMARY KEY,
    ProductID INT,
    WarehouseID INT,
    Stock INT
);

CREATE TABLE Warehouses (
    WarehouseID INT PRIMARY KEY,
    Location NVARCHAR(200)
);

-- Dùng Products để check
INSERT INTO Inventory (ProductID, WarehouseID, Stock)
SELECT ProductID, 1, 0
FROM Products;
