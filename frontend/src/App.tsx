import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Investigation } from "./pages/Investigation";

const qc = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <Investigation />
    </QueryClientProvider>
  );
}
