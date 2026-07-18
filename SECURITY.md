# Security Policy

Poké Starters is a fully client-side static site with no backend, no accounts,
and no user data collection, so the attack surface is small. Still, if you find
a security issue, we would like to know.

## Reporting a vulnerability

Please **do not** open a public issue for a security problem. Instead:

- Use GitHub's private [**Report a vulnerability**](https://github.com/drkostas/poke-starters/security/advisories/new) flow, or
- Email **gkos.mldev@gmail.com** with the details and steps to reproduce.

You can expect an acknowledgement within a few days. Once the issue is confirmed
and fixed, we are happy to credit you in the release notes if you would like.

## Scope

In scope: anything that lets a page or a crafted share-link run unexpected code,
exfiltrate data, or break the integrity of the deployed site.

Out of scope: the accuracy of the Pokémon game data, and issues that require a
user to paste hostile content into their own browser console.
