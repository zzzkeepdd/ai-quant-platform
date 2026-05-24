// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { BrowserRouter } from "react-router-dom";
import { expect, test } from "vitest";
import App from "./App";

test("渲染主标题", () => {
  render(
    <BrowserRouter>
      <App />
    </BrowserRouter>
  );
  expect(screen.getByText("AI量化自动交易平台")).toBeInTheDocument();
});
