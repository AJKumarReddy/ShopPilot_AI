import { expect, test } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  const response = await request.get("/api/v1/cart");
  const cart = await response.json();
  for (const item of cart.items || [])
    await request.delete(`/api/v1/cart/items/${item.id}`);
});

test("search, compare, cart, explicit confirmation and inventory update", async ({
  page,
  request,
}) => {
  await page.goto("/");
  const input = page.getByRole("textbox", { name: "Your shopping request" });
  await input.fill(
    "I'm looking for wireless noise-cancelling headphones under $150 with good battery life.",
  );
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByRole("log")).toContainText("I found 5 options", {
    timeout: 30000,
  });
  await expect(page.getByTestId("product-card")).toHaveCount(5);
  await input.fill("Compare the first and third");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(
    page.getByRole("dialog", { name: "A closer look" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close A closer look" }).click();
  await input.fill("Add the first one to my cart");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByRole("log")).toContainText("Your cart has 1 item");
  const cart = await (await request.get("/api/v1/cart")).json();
  const id = cart.items[0].product.id;
  const beforeStock = (
    await (await request.get(`/api/v1/products/${id}`)).json()
  ).inventory.stock_quantity;
  const beforeOrders = (await (await request.get("/api/v1/orders")).json())
    .orders.length;
  await input.fill("Checkout");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(
    page.getByRole("dialog", { name: "One last look" }),
  ).toBeVisible();
  expect(
    (await (await request.get("/api/v1/orders")).json()).orders.length,
  ).toBe(beforeOrders);
  await page.getByRole("button", { name: "Yes, place the order" }).click();
  await expect(page.getByText("Good find. It's confirmed.")).toBeVisible();
  expect(
    (await (await request.get(`/api/v1/products/${id}`)).json()).inventory
      .stock_quantity,
  ).toBe(beforeStock - 1);
  expect(
    (await (await request.get("/api/v1/orders")).json()).orders.length,
  ).toBe(beforeOrders + 1);
});

test("checkout without confirmation creates no order", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Add to cart", exact: true })
    .first()
    .click();
  await expect(page.getByText("Added to your shopping bag.")).toBeVisible();
  const before = (await (await request.get("/api/v1/orders")).json()).orders
    .length;
  await page.getByRole("button", { name: /Open shopping bag/ }).click();
  await page.getByRole("button", { name: /Review checkout/ }).click();
  await expect(
    page.getByText("Nothing has been ordered yet.", { exact: false }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Keep shopping", exact: true })
    .click();
  expect(
    (await (await request.get("/api/v1/orders")).json()).orders.length,
  ).toBe(before);
  const checkout = await (
    await request.post("/api/v1/checkout/prepare")
  ).json();
  const denied = await request.post("/api/v1/checkout/confirm", {
    data: {
      checkout_session_id: checkout.id,
      confirmation_token: checkout.confirmation_token,
      confirmed: false,
      idempotency_key: checkout.id,
    },
  });
  expect(denied.status()).toBe(422);
  expect(
    (await (await request.get("/api/v1/orders")).json()).orders.length,
  ).toBe(before);
});

test("mobile layout has no horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("textbox", { name: "Your shopping request" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
