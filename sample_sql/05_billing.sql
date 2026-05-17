-- Tạo hóa đơn tháng
CREATE TABLE Invoices (
    InvoiceID INT PRIMARY KEY,
    CustomerID INT,
    TotalAmount DECIMAL(18,2),
    InvoiceDate DATETIME
);

INSERT INTO Invoices (CustomerID, TotalAmount, InvoiceDate)
SELECT
    o.CustomerID,
    SUM(p.Price * oi.Quantity),
    GETDATE()
FROM Orders o
JOIN OrderItems oi ON o.OrderID = oi.OrderID
JOIN Products p ON oi.ProductID = p.ProductID
JOIN Customers c ON o.CustomerID = c.CustomerID
WHERE MONTH(o.OrderDate) = MONTH(GETDATE())
GROUP BY o.CustomerID;
