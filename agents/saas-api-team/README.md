# EdgarTools SAAS API Development Team

## Overview

This directory contains specialized agent definitions for building SAAS and data APIs on top of edgartools. Each agent represents a role with specific expertise, tools, and responsibilities in the development lifecycle.

## Team Structure

```
SAAS API Development Team
├── product-manager           # Product strategy, requirements, roadmap
├── senior-backend-engineer   # Core API development, architecture
├── infrastructure-engineer   # Deployment, scaling, DevOps
├── api-tester               # Testing, validation, quality assurance
├── finance-expert           # Financial domain expertise, data validation
├── performance-engineer     # Optimization, monitoring, scalability
├── code-reviewer            # Code quality, security, best practices
├── devsecops-engineer       # Security automation, compliance monitoring
├── technical-writer         # API documentation, developer guides
└── site-reliability-engineer # Reliability, incident response, SLOs
```

## Agent Interaction Patterns

### Development Workflow
1. **Product Manager** defines requirements and priorities
2. **Senior Backend Engineer** implements core functionality
3. **Finance Expert** validates financial calculations and domain logic
4. **Code Reviewer** ensures code quality and security
5. **DevSecOps Engineer** integrates security throughout development
6. **API Tester** validates functionality and edge cases
7. **Performance Engineer** optimizes for scale and speed
8. **Infrastructure Engineer** handles deployment and operations
9. **Site Reliability Engineer** ensures reliability and incident response
10. **Technical Writer** creates comprehensive documentation

### Communication Protocols
- All agents work with shared context from the Financial API Design Document
- Agents can request collaboration from other team members
- Each agent maintains expertise-specific documentation
- Cross-functional reviews required for major changes

## Usage

Each agent can be invoked individually or as part of coordinated workflows:

```bash
# Individual agent invocation
python -m agents.saas_api_team.product_manager "Define MVP requirements"

# Coordinated workflow
python -m agents.saas_api_team.workflow "Implement user authentication"
```

## Shared Resources

- **Design Document**: `/internal/docs/planning/financial-api-design.md`
- **EdgarTools Codebase**: Core library for financial data
- **Test Data**: Sample companies and financial scenarios
- **Infrastructure**: Deployment configurations and monitoring

## Quality Gates

Each agent enforces specific quality criteria:

- **Product**: Requirements clarity, user value
- **Backend**: Code quality, API design, security
- **Infrastructure**: Reliability, scalability, monitoring
- **Testing**: Coverage, edge cases, performance
- **Finance**: Data accuracy, compliance, domain correctness
- **Performance**: Response times, throughput, resource usage
- **Review**: Security, maintainability, best practices
- **DevSecOps**: Security automation, compliance monitoring, vulnerability management
- **Technical Writer**: Documentation completeness, developer experience, content quality
- **Site Reliability**: Service level objectives, incident response, system reliability