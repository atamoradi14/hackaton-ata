# Current HIRDS access gate

Verified on 14 October 2026 against the official
[HIRDS on DataHub page](https://data.niwa.co.nz/pages/hirds-on-datahub): the
former `hirds.niwa.co.nz` application redirects to Earth Sciences NZ DataHub.
An account and a declared purpose are required before obtaining the rainfall
tables. The user confirmed no DataHub account/credentials are available yet.
LINZ and OpenTopography keys cannot provide this access.

Manual next step: register/sign in through DataHub and obtain the HIRDS
depth-duration-frequency table for the verified site's point. Location and
coordinate provenance are saved privately in `data/processed/site/site_manifest.json`.
Use a purpose consistent with the local research/hackathon prototype. Do not
paste passwords or tokens into chat or commit them; a local export file is enough.

After acquisition, verify coordinate, units, HIRDS version, return periods/AEP,
climate scenario, source/licence and any uncertainty tables. Selecting an event
duration and temporal rainfall pattern is a separate modelling decision; do not
substitute the synthetic fixture's 36 mm/hr into the site model. Check the
hyetograph's integrated rainfall against the selected official depth.

The final hydraulic domain and outlet/boundary heads also remain unverified.
D8 screening retained local pits and ignored drainage/building/structure effects;
it is not sufficient to prove domain convergence or dynamic storm continuity.
No real property flood run, calibration or flood-risk verdict is produced at
this gate. Continue only with explicitly reviewable source/scenario assumptions.
