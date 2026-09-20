import { test, expect } from "@playwright/test";

/**
 * These tests drive the real UI against the real backend, which is expected
 * to already be indexed with live messages from Azure AI Search and to have
 * Azure OpenAI chat configured (see ../.env). They exercise the same flows
 * verified manually during Phase 3/4 development.
 */

test.describe("Smart Messages Manager", () => {
  test("shows Gmail connection status", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("connection-state")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Smart Messages Manager" })).toBeVisible();
  });

  test("searches real messages already indexed via Gmail sync", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("searchbox", { name: "Search query" }).fill("Goa trip hotel");
    await page.getByRole("button", { name: "Search", exact: true }).click();

    const results = page.getByTestId("search-results").locator("li");
    await expect(results.first()).toBeVisible({ timeout: 30_000 });
  });

  test("answers a grounded question with citations", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("textbox", { name: "Question" }).fill("What hotel did we book for Goa?");
    await page.getByRole("button", { name: "Ask", exact: true }).click();

    const answer = page.getByTestId("chat-answer");
    await expect(answer).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("evidence-badge")).toHaveText("Evidence found");
    await expect(page.getByTestId("citations").locator("li").first()).toBeVisible();
  });

  test("returns no-evidence for an unrelated question", async ({ page }) => {
    await page.goto("/");
    await page
      .getByRole("textbox", { name: "Question" })
      .fill("What is my flight number to Paris?");
    await page.getByRole("button", { name: "Ask", exact: true }).click();

    const answer = page.getByTestId("chat-answer");
    await expect(answer).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("evidence-badge")).toHaveText("No evidence");
  });
});
