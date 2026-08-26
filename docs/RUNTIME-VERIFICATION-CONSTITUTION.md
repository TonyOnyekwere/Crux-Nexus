# CRUXNEXUS RUNTIME VERIFICATION CONSTITUTION

1. CruxNexus SHALL NOT require local runtime execution as a development
   or deployment prerequisite.

2. Developer laptops SHALL NOT be treated as authoritative runtime
   environments.

3. CI verification SHALL execute against ephemeral CI-managed
   infrastructure where required.

4. Railway staging SHALL be the primary application runtime verification
   environment before production.

5. Production code paths SHALL NOT diverge from verification code paths.

6. Mock payment providers, fake financial success responses, placeholder
   production adapters, and simulated banking confirmations are forbidden
   in production architecture.

7. Automated verification is permitted and required where it validates
   real application invariants against real implementations. Automated
   verification SHALL NOT introduce alternative application logic.

8. The absence of local execution SHALL NOT justify bypassing migration,
   tenant isolation, authorization, security, or runtime verification.

9. Environment configuration SHALL be injected by the authoritative
   deployment environment and SHALL NOT be hardcoded into application code.

10. Railway runtime evidence SHALL take precedence over assumptions made
    from static code inspection.
