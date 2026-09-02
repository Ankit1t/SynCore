"use client";

import { motion, type HTMLMotionProps } from "framer-motion";

interface CardProps extends HTMLMotionProps<"div"> {
  interactive?: boolean;
}

export function Card({ interactive = false, className = "", children, ...props }: CardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 260, damping: 26 }}
      whileHover={interactive ? { scale: 1.01, y: -2 } : undefined}
      className={`rounded-2xl border border-line bg-surface shadow-soft ${className}`}
      {...props}
    >
      {children}
    </motion.div>
  );
}
