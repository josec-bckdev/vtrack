module.exports = {
  types: [
    { value: 'feat',     name: 'feat:     A new feature' },
    { value: 'fix',      name: 'fix:      A bug fix' },
    { value: 'docs',     name: 'docs:     Documentation only changes' },
    { value: 'style',    name: 'style:    Code style changes (formatting, semicolons, etc)' },
    { value: 'refactor', name: 'refactor: Code change that neither fixes a bug nor adds a feature' },
    { value: 'perf',     name: 'perf:     Performance improvements' },
    { value: 'test',     name: 'test:     Adding or updating tests' },
    { value: 'build',    name: 'build:    Changes to build system or dependencies' },
    { value: 'ci',       name: 'ci:       CI configuration changes' },
    { value: 'chore',    name: 'chore:    Other changes that don\'t modify src or test files' },
    { value: 'revert',   name: 'revert:   Revert a previous commit' }
  ],

  scopes: [
    { name: 'auth' },
    { name: 'api' },
    { name: 'ui' },
    { name: 'db' },
    { name: 'config' },
    { name: 'deps' }
  ],

  // Allow custom scopes
  allowCustomScopes: true,
  allowBreakingChanges: ['feat', 'fix', 'refactor', 'perf'],

  // Subject settings
  subjectLimit: 50,
  
  // Skip questions you don't want
  skipQuestions: [],

  // Message templates
  messages: {
    type: "Select the type of change you're committing:",
    scope: '\nDenote the SCOPE of this change (optional):',
    customScope: 'Denote the custom SCOPE:',
    subject: 'Write a SHORT, IMPERATIVE description (max 50 chars):\n',
    body: 'Provide a LONGER description (optional). Use "|" for line breaks:\n',
    breaking: 'List any BREAKING CHANGES (optional):\n',
    footer: 'List any ISSUES CLOSED by this change (optional). E.g.: #31, #34:\n',
    confirmCommit: 'Are you sure you want to proceed with the commit above?'
  }
};