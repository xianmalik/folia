% Identification
\ProvidesClass{xianmalik}[2026/03/29 v1.1.0 xianmalik]
\NeedsTeXFormat{LaTeX2e}

% Class options
\DeclareOption{draft}{\setlength\overfullrule{5pt}}
\DeclareOption{final}{\setlength\overfullrule{0pt}}
\DeclareOption*{%
  \PassOptionsToClass{\CurrentOption}{article}
}
\ProcessOptions\relax
\LoadClass{article}

% Packages
% tables, lists, alignment, layout, header/footer, colors, conditionals, icons
\RequirePackage{array}
\RequirePackage{enumitem}
\RequirePackage{ragged2e}
\RequirePackage{geometry}
\RequirePackage{fancyhdr}
\RequirePackage{xcolor}
\RequirePackage{xifthen}
\RequirePackage{etoolbox}
\RequirePackage{fontawesome5}

% paragraph spacing and hyperlinks
\RequirePackage{parskip}
\RequirePackage[hidelinks,unicode,pdfpagelabels=false]{hyperref}
\hypersetup{%
  pdftitle={CV of Malik Zubayer Ul Haider},
  pdfauthor={Malik Zubayer Ul Haider},
  pdfsubject={Resume},
  pdfkeywords={Resume, CV, Software, Engineer}
}
\RequirePackage{bookmark}

% Directory configuration (backwards compatibility)
\newcommand*{\fontdir}[1][fonts/]{\def\@fontdir{#1}}

% Core modules
\input{core/fonts}
\input{core/layout}
\input{core/colors}
\input{core/styles}
\input{core/commands}
\input{core/structure}
