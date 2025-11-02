# CDS Console

The CDS Console launches SMART-on-FHIR-compliant applications.

When a clinician launches an application via the CDS Console from CPRS,
the container connects to the CCOW Vault and retrieves the patient context.
The context is then extrapolated into a SMART on FHIR launch context
and passed into the application via a URL query parameter.
Further updates to the patient context are passed via messaging to opened applications.
The application will use this launch context when connecting to and authorizing with a downstream FHIR server.

Got general questions? You can reach the CDS Platform team on the DVSA Slack channel, at `#cds-platform-public`.

### Necessary information for integration
To onboard your application, please add to the `APPLICATIONS` list in each `config/config-<env>.js` file in which your app should be enabled. An example json blob is below:

```typescript jsx
    {
      title: 'Covid Patient Manager',
      code: 'cpm',
      shortName: 'CPM',
      shortDescription: 'Provides disposition recommendations based on patient health data',
      oneLiner: 'Leverage real-time patient data to evaluate and address issues associated with COVID-19 for your patients.',
      benefitsToClinicians: [
        'Classifies COVID-19 patients by disease severity and assesses risk for severe disease progression',
        'Generates recommendations from the American College of Emergency Room Physicians\' (ACEP) Emergency Department COVID-19 Management Tool',
        'Recommendations provided can be easily exported to notes',
      ],
      icon: 'smart-container/images/cpm-icon.webp',
      baseUrl: 'https://cds.med.va.gov/cpm/launch.html',
      userGuideUrl: 'https://dvagov.sharepoint.com/sites/CDSProgramTeam/SitePages/CPM/CPM-User-Guide.aspx';
      moreInformationUrl: 'https://dvagov.sharepoint.com/sites/CDSProgramTeam/SitePages/CPM/CPM-Learn-More.aspx';
      customLinks: [
        {
          linkDescription: 'Custom Link for CPRS',
          linkType: 'Sharepoint Page',
          url: 'https://dvagov.sharepoint.com/sites/CDSProgramTeam/SitePages/CPRS-Booster.aspx',
        },
      ],
      ccowConnected: true,
      hasCcowFallback: false,
      onCcowContextChange: 'send_message', // options are 'send_message' or 'update_location'
      openLocation: 'embedded_tab', //options are 'embedded_tab' or 'browser_tab'
      hasCdsHeader: true, //defaults to false
      warnBeforeClosing: false, //defaults to false
      filter: {
        enabledByDefault: true,
        exemptStations: ["100"],
      },
      doNotCloseOnSessionExp: false //defaults to false,
      allowMicrophoneAccess: false // defaults to false
    },
```
#### We need: ####
 - *title*: A title for your application
 - *code*: A simple code for your application ie. COVID-19 Patient Manager is cpm (used as a url parameter for automatically launching your app)
 - *shortName*: A short name for your application ie. CPM (used to display on small spaces like the tab title)
 - *shortDescription*: A short description of your application (displayed on the app tile)
 - *oneLiner*: A one liner or longer description (displayed in the side drawer when "more information" button is clicked)
 - *benefitsToClinicians*: Bulleted list of benefits to clinicians (displayed in the side drawer when "more information" button is clicked)
 - *userGuideUrl*: Link for users to view a user guide for your application on SharePoint
 - *moreInformationUrl*: Link for users to read more information about your application on SharePoint
 - *customLinks*: An optional array of custom links for your application. We recommend keeping the link list short (up to 5 or 6) to ensure that the list does not crowd other content on-screen. Each link should have a link description, link type, and url. The link type will be in brackets next to the link description, and should explain where you are linking the user.
 - *icon*: A main page screenshot of your application to use as an icon. The image is required to be in .webp format. Put your icon into `public/images/<your_webp_here>.webp`
 - *baseUrl*: The application url in Development, Stage, and Production environments.
 <!-- - Set `enabled` value to `true` to allow platform-wide access to your application.  -->
 - *ccowConnected*: Is your application CCOW connected?
 - *hasCcowFallback*: If your app is CCOW connected, will your it still be usable without CCOW (maybe it has a way for the user to select the patient)
 - *onCcowContextChange* On CCow context change do you want `send_message` (we will post a browser message) or `update_location` (we will reload your app with the updated url).
 - *openLocation*: Should the app open embedded within the Console page (default), or should it open in a separate browser tab?
 - *hasCdsHeader*: Does your app already implement the Design System's header component? If not, the Console will display it for consistency. This defaults to false
 - *warnBeforeClosing*: Should the console display a warning to users that they may have unsaved changes when they try to close your app? This defaults to false
 - *filter*:
    - You have the option of using filter settings to control which specific VAMC stations the application is available on.
    - The filter property is optional. If no filter property is specified, your application will be enabled by default for all VAMC stations.
    - To update filter settings, please revise settings accordingly and submit a pull request.
      - Specify whether your application should be enabled by default for all VAMC stations (`true`) or disabled by default (`false`).
      - Optional: Specify whether there are any stations that are exempt from the default setting by adding the 3-digit station ID to the exemptStations array, as a string.
      - Please note that we do not filter by 5-digit station numbers, and will truncate any 5-digit stations in the configuration to the 3-digit version. So, for example, if your filter includes Station 528A6 (for Bath VA Medical Center), we will apply the filter for Station 528 instead.
 - *multiPatient*: Set it to true if your application is a multi-patient app. Doing so will remove patient icn in the launch context. This defaults to false
 - *doNotCloseOnSessionExp*: Set to true if your app cannot be interrupted by the Console closing it when the session expires (requires discussion)
 - *allowMicrophoneAccess*: Set to true if your app is embedded and needs microphone access (AI Scribe apps)



### What's in a launch context?

When the SOFC launches your application it uses a URL determined by a function. It includes a `launch` query parameter, which is used to encode patient information and enables integration with Lighthouse's Health APIs.

[As described in the Lighthouse documentation](https://developer.va.gov/explore/authorization/docs/authorization-code?api=clinical_health#requesting-authorization),
the value of this parameter is a Base64-encoded JSON object, containing the patient ICN, the VistA station number, and the "designated user":

For a single patient application, the launch context includes a patient icn, a sta3n number, and a duz number:

```json
{
  "patient": "1000720100V271387",
  "sta3n": "993",
  "duz": "11111323223232"
}
```

For a multi-patient application, the launch context includes only a sta3n number, and no patient icn or duz number:

```json
{
  "sta3n": "993"
}
```

#### Passing additional information to your application
When a SMART application is auto-launched, the console may pass additional information to the application by setting an `app_context` query parameter in the launch URL. This enables apps to receive custom context data upon launch, with potential uses such as deep linking or other app-specific configurations.

To use this feature, ensure that your application accepts an `app_context` query parameter. Then you can configure any links to your application through the CDS Console to forward your context to the application. App teams using this feature must ensure the optional `app_context` parameter is retained through the Lighthouse authentication flow's redirects, as it is not handled automatically. We recommend sending the information as base-64 encoded data.

##### Security Considerations

When working with URLs, it's important to be aware of the VA's security protections against injection attacks. These protections prevent certain characters and structures from being included in URLs.

Base64 encoding allows you to securely pass objects in URLs, without using any characters that might be blocked for security reasons.

**Note:** Always ensure that any data passed in URLs is properly encoded to avoid potential security issues.

For example, when a user navigates to an application via the console, with a link containing the app context:

> `https://cds.med.va.gov/smart-container/index.html?sta3n=500&duz=983&app=exampleApp&app_context=exampleContext`

then the CDS Console will launch the application with the following URL:

 > `https://cds.med.va.gov/exampleApp/launch?iss=https://api.va.gov/services/clinical-fhir/v0/r4/&launch=yyyyy&app_context=exampleContext`

##### Implementation Notes
- The console allows case-insensitive query parameter keys, as long as the spelling is correct. For example, we'll accept both `app_context` and `APP_CONTEXT`. However, the console will always use lowercase `app_context` for the application launch URL.

- The console will not modify the value of the app_context parameter. The value will be passed to the application as is.

## Requesting Patient Context Change from the Console
Visit [Patient Context Change Request Documentation](./docs/patient-context-change.md)


## Smoke tests
To include your application in the smoke tests, add the app tile to the function `appTilesAreVisible()` in `./playwright/pages/console-ui-page.ts`. This function is called by the smoke tests, which will test that the tile has loaded. Only applications in production should be added.

### Further smoke test [documentation](docs/smoke-tests.md):
- Running the smoke tests [locally](docs/smoke-tests.md#running-the-tests-locally) and in the [pipeline](docs/smoke-tests.md#running-the-tests-in-the-pipeline)
- [Traces for Pipeline Runs](docs/smoke-tests.md#capturing-reporting-and-tracing-from-playwright-tests-in-ci)
- [FAQ](docs/smoke-tests.md#FAQ)
- [Troubleshooting](docs/smoke-tests.md#Troubleshooting)

## Running, testing, and developing the container

1. Install Node version as defined in [`.node-version`](.node-version)
1. Enable corepack with `corepack enable`
1. Configure github token for github npm registry:
   * Have a personal github token ready [described further down the page](#create-github-token)
   * Create or edit your `.env.yarn` file by copying `.env.template` and adding your token
1. Run `yarn install` to install the required libraries.

> Note: If on your GFE you will have to run your terminal with Admin privileges and disconnect from the VPN to install yarn.

### Launching the Application

* Start the app locally (`yarn start`)

Runs the app in the development mode.\
Open [http://localhost:3000](http://localhost:3000) to view it in the browser.

The page will reload if you make edits.\
You will also see any lint errors in the console.

The frontend depends on a backend service (CDS Console API) for authorization and other functionality.\
Locally, you can run the mock api stubs : `yarn ma`

> `yarn ma` will run yarn install in the mockApis folder, then start the mock api server.

> You can ignore certain mock apis by adding `--ignore [apiName]` to the command.\
> For example, to ignore the Task Management API, run `yarn ma -i taskManagementApi`

### `yarn test`

Launches the test runner in the interactive watch mode.\
See the section about [running tests](https://facebook.github.io/create-react-app/docs/running-tests) for more information.

### `yarn lint`

Runs static code analysis with ESLint. There is also a [pre-commit](https://pre-commit.com) hook to fix linting issues.

The smoke tests have [their own linter config](docs/smoke-tests.md#linting-the-smoke-tests).

### `yarn format`

Runs Prettier to automatically format your code according to a specified style guide. This helps ensure that the codebase maintains a consistent style and improves readability.

### Running the production build locally with Docker & NGINX
* Have a github token ready [described further down the page](#create-github-token)
* Run `docker login ghcr.io -u [your github username]`
  * Enter your token as the password when prompted
  * This step is required so you can pull the private base Docker image we use
* Run `npm login --scope=@department-of-veterans-affairs --registry=https://npm.pkg.github.com` use your github username and use your token for the password
* Build the docker image: `GITHUB_TOKEN="xxxx" yarn build:docker`
  * Replace xxxx with your github token. This is needed so that the private Clinical Design System npm packages can be installed on the docker image. The token will not persist on the image.
  * If you are on a MAC with an Mx chip, and you get an error about arm vs amd, run `GITHUB_TOKEN="xxxx" yarn build:docker:mac` instead
* Run the docker image: `docker run -p 8080:8080 [name]:[tag]`
* View the app on http://localhost:8080/smart-container/
  * You can also access it without /smart-container/, but some of the nginx rules are specific to that path
* Note: If you are making frequent changes locally but need to use the production build, it's faster to run yarn run build yourself and take the first layer out of the dockerfile. The current Dockerfile takes about 2.5 min to build, but without the first layer it only takes a second or two.


#### Commit Message Template
```
Does this cool thing
department-of-veterans-affairs/cds-platform#issuenumber
Co-author: First Last <email.address@example.com>
```

## Install pre-commit hooks
1.Install pre-commit -- see [pre-commit](https://github.com/department-of-veterans-affairs/cds-platform/blob/main/docs/PreCommit.md) for more information.
1. Run `pre-commit install` to install the pre-commit hooks.

## Security

### Scanning for Vulnerabilities

You can run `yarn audit-deploy` to scan for vulnerabilities in the installed NPM modules that are deployed to production.

### Resolving Vulnerabilities

If you find some vulnerabilities after [scanning for them](#scanning-for-vulnerabilities), then they will need to be resolved. This can be accomplished in a few ways:

1. Ideally, [upgrade the module](https://classic.yarnpkg.com/lang/en/docs/selective-version-resolutions/) to a version where the vulnerability has been fixed
1. If a fix is _not_ available, then assess whether the vulnerability applies to our use case:
    1. Run `yarn info -AR [name of module]` and see where the module is being used:
   ```
    $ yarn info -AR braces

    | > yarn info -AR braces
    └─ braces@npm:3.0.3
       ├─ Version: 3.0.3
       │
       └─ Dependencies
          └─ fill-range@npm:^7.1.1 → npm:7.1.1
    ```
    1. In this example, the vulnerable `braces@3.0.2` module is only used by the `@babel/cli` build module. Since the build process is never exposed to the user, only to developers and to the build pipeline, it could be argued that this vulnerability can be ignored
    1. If the vulnerability can be ignored:
        1. Make note of this in the response report
        1. Add the module to an _ignore_ list for the scanner
        1. Verify that the module no longer shows up in vulnerability reports as an unresolved issue
1. If a fix is not available and the vulnerability _could_ be plausibly exploited, then report it as "not fixable"

### Trivy scans for image Vulnerabilities in GitHub Actions

As an extra point of security we have a built-in scanner as part of the pipeline.
Before tagging and pushing to ECR can happen, the container image must be scanned for vulnerable libraries to prevent a vulnerable image from being deployed to the ECS Cluster.
GitHub Actions defines Commands, Jobs, and Workflows in this order in its `.github/workflows/app-ci.yml` file.

When the security scan fails, the pipeline will stop the image from being sent to the ECR.

### Using trivy to resolve image Vulnerabilities in GitHub Action
To ignore a specific vulnerability (ex: in a situation where a patch for a vulnerable dependency is not available yet):
- Copy and paste the full CVE code from the trivy scan output from GitHub Action into the `.trivyignore` file. Each CVE should be in its own line.
    - ex:
  ```
  CVE-2019-1757
  CVE-2015-8103
  CVE-2015-4852
  ...
  ```
- Push the updated `.trivyignore`
Note: Make sure to write a note on the tech huddle board/otherwise notify the team to revisit the vulnerability to continuously understand when a patch or other solution may become available.

### Content Security Policy
* The CSP header for the production (deployed) build is set in the NGINX default.conf file
* The CSP header for the development (local) build is set in the `vite.config.mts` file
* Notes:
  * CSS files are referenced as links in deployed env, and allowed in CSP with 'self'
  * CSS files are added as embedded style tags in the local env, which would require either nonce or hash
  * We set a meta tag with a value of 'PLACEHOLDER_NONCE' in our vite config. Vite will then inject the nonce value in all `<script>` and `<style>` tags. In the deployed env, this gets replaced by NGINX with a unique id for each request. Locally, it stays static.
  * In nonce.js, we read the dynamic nonce value and put it in a global variable that our js can access.
  * Emotion (CSS as JS library) generates style tags and dynamically inserts the content and nonce when the page is loaded, so we give it our dynamic nonce with its createCache function

## Create GitHub token
You will need a personal github token for two things:
* Pulling the CDSP NGINX base Docker image
* Installing the Clinical Design System npm packages

See [Authenticating to the Container registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#authenticating-to-the-container-registry) and [Creating a fine-grained personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)

This mostly follows "Creating a fine-grained personal access token", but deviates when creating a new token. This section uses the "classic" token instead of the "new" fine-grain token.

Create a new token (the following assumes classic and not fine-grain token)
1. Add a note
2. Set "No expiration" for the "Expiration" drop-down
3. Check "read:packages" and "repo"
4. Click "Generate token"
5. Copy the generated token and put it somewhere (like 1Password)
6. In a terminal run the following (replace the username with your github username):
   1. `docker login ghcr.io -u USERNAME`
   2. When prompted, type/paste the GitHub token.
      - Note: You may need to delete this line from your `~/.docker/config.json`:
      ```
      "credStore": "desktop"
      ```

## Other docs
* [Feature flag usage](docs/feature-flags.md)
* [Known console warnings and errors](docs/console-warnings.md)
* [Datadog ECS App Metrics Dashboard](https://cpm.ddog-gov.com/dashboard/6k9-5pe-yxj/cds-console-ecs-app-metrics-dashboard)
