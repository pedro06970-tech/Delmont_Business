import { redirect } from "next/navigation";

// The request proxy resolves authenticated visits before this fallback renders.
export default function Home() {
  redirect("/login");
}
