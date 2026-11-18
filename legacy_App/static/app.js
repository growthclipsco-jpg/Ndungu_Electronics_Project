// Interactive client-side helpers for Ndungu Electronics IMS
document.addEventListener("DOMContentLoaded", () => {
  // Confirm actions with data-confirm
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      const msg = form.getAttribute("data-confirm") || "Are you sure?";
      if (!confirm(msg)) {
        e.preventDefault();
      }
    });
  });

  // Dynamic price calculation on Sell screen
  const qtyInput = document.getElementById("quantity");
  const totalElem = document.getElementById("sale-total");
  if (qtyInput && totalElem) {
    const unitPrice = parseFloat(qtyInput.dataset.unitPrice || "0");
    const update = () => {
      const qty = parseInt(qtyInput.value, 10) || 0;
      const total = qty * unitPrice;
      totalElem.textContent = "Kes. " + total.toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
    };
    qtyInput.addEventListener("input", update);
  }
});
