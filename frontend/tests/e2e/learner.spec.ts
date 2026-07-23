import { expect, test } from "@playwright/test";

import { LEARNER_STATE_PATH } from "./auth-files";

test.use({ storageState: LEARNER_STATE_PATH });

test("learner dashboard and flashcard study flow work", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Open Admin Panel" })).toHaveCount(0);
  await expect(page.getByText("Words Learned")).toBeVisible();

  await page.goto("/flashcards?view=create");
  const createSetSection = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Create Flashcard Set" }),
  });
  await createSetSection.getByLabel("Name", { exact: true }).fill("UI Travel Set");
  await createSetSection.getByLabel("Description").fill("Created during browser coverage.");
  await createSetSection.getByLabel("Tags").fill("travel, ui");
  await createSetSection.getByRole("button", { name: "Create Set" }).click();

  const createdSet = page.locator("article").filter({ hasText: "UI Travel Set" });
  await expect(createdSet).toBeVisible();
  await Promise.all([
    page.waitForURL(/\/flashcards\/[^/]+$/),
    createdSet.getByRole("link", { name: "Manage Cards" }).click(),
  ]);

  await page.getByLabel("Korean").fill("기차");
  await page.getByLabel("English").fill("train");
  await page.getByLabel("Notes").fill("Useful transportation word.");
  await page.getByLabel("Card Tags").fill("travel");
  await page.getByRole("button", { name: "Add Card" }).click();
  await expect(page.locator('input[value="기차"]').first()).toBeVisible();
  await page.getByRole("button", { name: "Star", exact: true }).click();
  await expect(page.getByRole("button", { name: "Starred", exact: true })).toBeVisible();

  await page.goto("/flashcards?view=sets");
  await Promise.all([
    page.waitForURL(/\/flashcards\/[^/]+\/study$/),
    page
      .locator("article")
      .filter({ hasText: "UI Travel Set" })
      .getByRole("link", { name: "Study" })
      .click(),
  ]);
  await expect(page.getByRole("heading", { name: "UI Travel Set" })).toBeVisible();
  await expect(page.getByText("train")).toHaveCount(0);
  await page.getByRole("button", { name: /Click to reveal details/ }).click();
  await expect(page.getByText("English:")).toBeVisible();
  await expect(page.getByText("train")).toBeVisible();
  await expect(page.getByRole("button", { name: "Remove star from flashcard" })).toBeVisible();
  await page.getByRole("button", { name: "Remove star from flashcard" }).click();
  await expect(page.getByRole("button", { name: "Star flashcard" })).toBeVisible();
  await page.getByRole("button", { name: "Mark Easy" }).click();
  await expect(page.getByText("Session complete")).toBeVisible();
});

test("assignment flows validate inputs and support text, pdf, and manual flows", async ({ page }) => {
  await page.goto("/assignments");

  const textSection = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Generate From Text" }),
  });
  await textSection.getByRole("button", { name: "Generate From Text" }).click();
  await expect(textSection.getByText("Enter a title before generating an assignment.")).toBeVisible();

  await textSection.getByLabel("Title").fill("Dialogue Practice");
  await textSection.getByLabel("Source Text").fill("안녕하세요. 저는 학생입니다.");
  await textSection.getByRole("button", { name: "Generate From Text" }).click();
  await expect(page.getByText("Dialogue Practice")).toBeVisible();

  const pdfSection = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Generate From PDF" }),
  });
  await pdfSection.getByLabel("Title").fill("Worksheet Import");
  await pdfSection
    .getByLabel("PDF File")
    .setInputFiles({
      name: "worksheet.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 worksheet"),
    });
  await pdfSection.getByRole("button", { name: "Generate From PDF" }).click();
  await expect(page.getByText("Worksheet Import")).toBeVisible();

  const manualSection = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Create Manual Assignment" }),
  });
  await manualSection.getByLabel("Title").fill("Manual Browser Assignment");
  await manualSection.getByLabel("Prompt").fill("Choose hello in Korean.");
  await manualSection.getByLabel("Options").fill("안녕하세요");
  await manualSection.getByLabel("Correct Answer").fill("안녕하세요");
  await manualSection.getByRole("button", { name: "Save Manual Assignment" }).click();
  await expect(manualSection.getByText("Question 1 needs at least two options.")).toBeVisible();

  await manualSection.getByLabel("Options").fill("안녕하세요, 학교");
  await manualSection.getByRole("button", { name: "Save Manual Assignment" }).click();

  const manualCard = page.locator("article").filter({ hasText: "Manual Browser Assignment" });
  await expect(manualCard).toBeVisible();
  await Promise.all([
    page.waitForURL(/\/assignments\/[^/]+$/),
    manualCard.getByRole("link", { name: "Open" }).click(),
  ]);

  await page.locator("select").first().selectOption("안녕하세요");
  await page.getByRole("button", { name: "Submit Assignment" }).click();
  await expect(page.getByText("Score:")).toBeVisible();
  const latestResult = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Latest Result" }),
  });
  await expect(latestResult.getByText("100%")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Grading History" })).toBeVisible();
  await page.getByRole("button", { name: "Redo Assignment" }).click();
  await expect(page.getByRole("button", { name: "Submit Assignment" })).toBeVisible();
});

test.use({ storageState: LEARNER_STATE_PATH, viewport: { width: 375, height: 812 } });

test("mobile navigation exposes learner links", async ({ page }) => {
  await page.goto("/dashboard");
  await page.getByRole("button", { name: "Menu" }).click();
  await expect(page.getByRole("link", { name: "View Sets" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Create Set" })).toBeVisible();
  await page.getByRole("link", { name: "Profile" }).click();
  await expect(page.getByText("Discord ID")).toBeVisible();
});
