"use client";

import Image from "next/image";
import { motion, type Variants } from "framer-motion";
import type { ReactNode } from "react";

/**
 * AuthShell — adapted from the Watermelon UI "auth-07" block (Design 7).
 * Source: https://registry.watermelon.sh/r/auth-07.json
 *
 * Original layout preserved:
 *   - split screen: left form panel + right image panel
 *   - header branding (absolute, top-left)
 *   - centered title/subtitle with motion stagger reveal
 *   - rounded-full inputs + dark gradient submit button styling
 *
 * Adapted for Carib Voices: brand text + image swapped for Caribbean theme;
 * the form body, title and footer are supplied via props so the same shell
 * powers register / sign-in / Google completion screens.
 */
const containerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.2 },
  },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 15 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { type: "spring", stiffness: 300, damping: 24 },
  },
};

export function MotionItem({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div variants={itemVariants} className={className}>
      {children}
    </motion.div>
  );
}

export interface AuthShellProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
  /** Optional node rendered above the form (e.g. Google button). */
  topExtra?: ReactNode;
  divider?: boolean;
}

export default function AuthShell({
  title,
  subtitle,
  children,
  footer,
  topExtra,
  divider = true,
}: AuthShellProps) {
  return (
    <div className="flex min-h-screen w-full bg-white font-sans text-neutral-950 antialiased selection:bg-neutral-900 selection:text-white relative">
      {/* Left Form Section */}
      <div className="flex w-full flex-col lg:w-1/2">
        {/* Header Branding */}
        <div className="p-6 md:p-10 absolute md:top-4 md:left-4 top-2 left-2 z-10">
          <span className="text-lg md:text-xl lg:text-2xl font-bold tracking-tight">
            CARIB <span className="text-emerald-600">VOICES</span>
          </span>
        </div>

        {/* Form Container */}
        <div className="flex flex-1 items-center justify-center p-6 md:p-10 mt-4 md:mt-8">
          <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            className="w-full max-w-[440px]"
          >
            <motion.div variants={itemVariants} className="mb-6 text-center">
              <h1 className="mb-1 text-3xl font-semibold tracking-tight text-neutral-900 md:text-4xl">
                {title}
              </h1>
              {subtitle && <p className="text-sm text-neutral-500">{subtitle}</p>}
            </motion.div>

            {topExtra && <motion.div variants={itemVariants} className="mb-4">{topExtra}</motion.div>}

            {divider && (
              <motion.div variants={itemVariants} className="relative mb-6 flex items-center">
                <div className="grow border-t border-neutral-200" />
                <span className="px-4 text-sm text-neutral-400">or</span>
                <div className="grow border-t border-neutral-200" />
              </motion.div>
            )}

            {children}

            {footer && (
              <motion.div variants={itemVariants} className="mt-5 text-sm text-neutral-500">
                {footer}
              </motion.div>
            )}
          </motion.div>
        </div>
      </div>

      {/* Right Image Section */}
      <div className="hidden lg:block lg:w-1/2 p-4">
        <div className="relative h-full w-full overflow-hidden rounded-[2rem] bg-emerald-900">
          <Image
            src="/caribbean-auth.svg"
            alt="A Caribbean coastline at golden hour"
            fill
            priority
            sizes="50vw"
            className="object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" />
          <div className="absolute bottom-6 left-6 right-6 text-white">
            <p className="text-sm font-medium opacity-90">Carib Voices</p>
            <p className="text-xs opacity-70">Collecting Jamaican speech, one voice note at a time.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
