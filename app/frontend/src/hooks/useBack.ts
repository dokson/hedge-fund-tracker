import { useLocation, useNavigate } from "react-router";

/**
 * Handler that goes back to the page the visitor came from, or to `fallback` when the app was
 * entered on this page (a shared link, a new tab) and there is nothing to go back to. The
 * router gives the first entry of a session the key `"default"`.
 */
export function useBack(fallback: string): () => void {
  const navigate = useNavigate();
  const { key } = useLocation();
  return () => {
    if (key === "default") void navigate(fallback);
    else void navigate(-1);
  };
}
