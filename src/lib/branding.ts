/**
 * FootyEdge AI Engine - Enterprise Intelligence Platform
 */

export const FootyEdgeBranding = {
  COMPANY_NAME: "FootyEdge AI",
  PRODUCT_NAME: "FootyEdge AI",
  BET9JA_FOCUS: true,
  TAGLINE: "Enterprise AI Engine | Multi-Agent Architecture | PostgreSQL",
  
  AGENTS: [
    { name: "Athena", role: "Data Ingestion" },
    { name: "Ares", role: "Team Strength" },
    { name: "Apollo", role: "Goal Distribution" },
    { name: "Hermes", role: "Value Detection" },
    { name: "Nike", role: "Kelly Calculator" },
    { name: "Zeus", role: "Orchestration" }
  ],
  
  getPoweredBy: () => {
    return {
      company: "FootyEdge AI",
      product: "FootyEdge AI",
      architecture: "Multi-Agent AI",
      database: "PostgreSQL",
      version: "1.0.0"
    };
  }
};
