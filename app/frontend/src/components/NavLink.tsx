import { NavLink as RouterNavLink, NavLinkProps } from "react-router-dom";
import { Ref } from "react";
import { cn } from "@/lib/utils";

interface NavLinkCompatProps extends Omit<NavLinkProps, "className"> {
  className?: string;
  activeClassName?: string;
  pendingClassName?: string;
  ref?: Ref<HTMLAnchorElement>;
}

function NavLink({
  className,
  activeClassName,
  pendingClassName,
  to,
  ref,
  ...props
}: NavLinkCompatProps) {
  return (
    <RouterNavLink
      ref={ref}
      to={to}
      className={({ isActive, isPending }) =>
        cn(className, isActive && activeClassName, isPending && pendingClassName)
      }
      {...props}
    />
  );
}

export { NavLink };
