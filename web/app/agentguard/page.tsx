import { AgentGuardPanel } from "@/components/agentguard/AgentGuardPanel";

export const metadata = {
  title: "AgentGuard — AP2 Trust Layer",
  description: "Deterministic CAN_PAY gate + AP2 mandates in front of live Razorpay UPI checkout.",
};

export default function AgentGuardPage() {
  return <AgentGuardPanel />;
}
