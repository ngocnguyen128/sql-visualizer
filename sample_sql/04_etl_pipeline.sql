-- ETL: đồng bộ tồn kho sau khi có đơn hàng mới
CREATE TABLE StagingOrders (
    OrderID INT,
    ProductID INT,
    Quantity INT,
    ProcessedAt DATETIME
);

-- Lấy đơn hàng chưa xử lý
INSERT INTO StagingOrders (OrderID, ProductID, Quantity, ProcessedAt)
SELECT oi.OrderID, oi.ProductID, oi.Quantity, GETDATE()
FROM OrderItems oi
JOIN Orders o ON oi.OrderID = o.OrderID
WHERE o.OrderDate >= DATEADD(HOUR, -1, GETDATE());

-- Cập nhật tồn kho
UPDATE Inventory
SET Stock = Stock - s.Quantity
FROM Inventory inv
JOIN StagingOrders s ON inv.ProductID = s.ProductID;
