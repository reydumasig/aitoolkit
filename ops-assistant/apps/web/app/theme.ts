import { createTheme } from "@mui/material/styles";

const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#2c5cff" },
    background: { default: "#f7f8fb" },
  },
  shape: { borderRadius: 10 },
  typography: {
    fontFamily:
      "var(--font-geist-sans), -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif",
  },
});

export default theme;
