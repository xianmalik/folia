% Identification
\ProvidesClass{xianmalik}[2025/09/20 v1.6.1 xianmalik Curriculum Vitae Class]
\NeedsTeXFormat{LaTeX2e}

% Class options
% Options for draft or final
\DeclareOption{draft}{\setlength\overfullrule{5pt}}
\DeclareOption{final}{\setlength\overfullrule{0pt}}
% Inherit options of article
\DeclareOption*{%
  \PassOptionsToClass{\CurrentOption}{article}
}
\ProcessOptions\relax
\LoadClass{article}

% Packages
% tables, lists, alignment, layout, header/footer, colors, conditionals, icons, fonts
\RequirePackage{array}
% handle list environment
\RequirePackage{enumitem}
% handle text alignment
\RequirePackage{ragged2e}
% configure page layout
\RequirePackage{geometry}
% make header & footer effeciently
\RequirePackage{fancyhdr}
% manage colors
\RequirePackage{xcolor}
% conditional helpers
\RequirePackage{xifthen}
\RequirePackage{etoolbox}
% icons
\RequirePackage{fontawesome5}

% fonts
\RequirePackage{fontspec}
\defaultfontfeatures{Ligatures=TeX}

\setmainfont[
  Path = font/,
  UprightFont = Inter-Variable.ttf,
  BoldFont = Inter-Variable.ttf,
  BoldFeatures = {RawFeature = {+wght=700}},
  RawFeature = {+wght=400}
]{Inter}

% paragraph spacing and hyperlinks
\RequirePackage{parskip}
% deal hyperlink
\RequirePackage[hidelinks,unicode,pdfpagelabels=false]{hyperref}
\hypersetup{%
  pdftitle={CV of Malik Zubayer Ul Haider},
  pdfauthor={Malik Zubayer Ul Haider},
  pdfsubject={Resume},
  pdfkeywords={Resume, CV, Software, Engineer}
}
% bookmarking
\RequirePackage{bookmark}

% Directory configuration (backwards compatibility)
\newcommand*{\fontdir}[1][fonts/]{\def\@fontdir{#1}}

% Layout
\geometry{left=2.0cm, top=1.5cm, right=2.0cm, bottom=2.0cm, footskip=.5cm}

% Header & Footer
\fancyhfoffset{0em}
% Remove head rule
\renewcommand{\headrulewidth}{0pt}
% Clear all header & footer fields
\fancyhf{}
% use fancyhdr
\pagestyle{fancy}

% Colors
\definecolor{white}{HTML}{FFFFFF}
\definecolor{black}{HTML}{000000}
\definecolor{darkgray}{HTML}{333333}
\definecolor{gray}{HTML}{5D5D5D}
\definecolor{lightgray}{HTML}{999999}
% Text colors
\definecolor{darktext}{HTML}{414141}
\colorlet{text}{darkgray}
\colorlet{graytext}{gray}
\colorlet{lighttext}{lightgray}
\colorlet{sectiondivider}{gray}
% Accent color
\definecolor{accentcolor}{HTML}{DC3522}

% Section color highlight toggle
\newbool{acvSectionColorHighlight}
\setbool{acvSectionColorHighlight}{true}

% Accent section color
\def\@sectioncolor#1#2#3{%
  \ifbool{acvSectionColorHighlight}{{\color{accentcolor}#1#2#3}}{#1#2#3}%
}

% Fonts
\newcommand*{\headerfont}{\fontspec{Inter}[RawFeature = {+wght=700}]}
\newcommand*{\headerfontlight}{\fontspec{Inter}[RawFeature = {+wght=300}]}
\newcommand*{\footerfont}{\fontspec{Inter}[RawFeature = {+wght=400}]}
\newcommand*{\bodyfont}{\fontspec{Inter}[RawFeature = {+wght=400}]}
\newcommand*{\bodyfontlight}{\fontspec{Inter}[RawFeature = {+wght=300}]}

% Styles
\newcommand*{\headerfirstnamestyle}[1]{{\fontsize{20pt}{1em}\headerfont\color{text} #1}}
\newcommand*{\headerlastnamestyle}[1]{{\fontsize{20pt}{1em}\headerfont\color{text} #1}}
\newcommand*{\headerpositionstyle}[1]{{\fontsize{7.6pt}{1em}\bodyfont\scshape\color{graytext} #1}}
\newcommand*{\headeraddressstyle}[1]{{\fontsize{7pt}{1em}\headerfontlight\color{lighttext} #1}}
\newcommand*{\headersocialstyle}[1]{{\fontsize{6.8pt}{1em}\headerfontlight\color{text} #1}}
\newcommand*{\footerstyle}[1]{{\fontsize{8pt}{1em}\footerfont\scshape\color{lighttext} #1}}
\newcommand*{\sectionstyle}[1]{{\fontsize{12pt}{1em}\bfseries\color{text} #1}}
\newcommand*{\paragraphstyle}{\fontsize{9pt}{1em}\bodyfontlight\upshape\color{text}}

% Entry styles
\newcommand*{\entrytitlestyle}[1]{{\fontsize{12pt}{1em}\headerfont\color{darktext} #1}}
\newcommand*{\entrypositionstyle}[1]{{\fontsize{6pt}{1em}\color{graytext} #1}}
\newcommand*{\entrydatestyle}[1]{{\fontsize{8pt}{1em}\bodyfont\slshape\color{graytext} #1}}
\newcommand*{\entrylocationstyle}[1]{{\fontsize{9pt}{1em}\bodyfont\slshape\color{graytext} #1}}
\newcommand*{\descriptionstyle}[1]{{\fontsize{9pt}{1em}\bodyfont\upshape\color{text} #1}}
\newcommand*{\metastyle}[1]{{\fontsize{8pt}{1em}\bodyfont\upshape\color{graytext} #1}}

% Skill styles
\newcommand*{\skilltypestyle}[1]{{\fontsize{10pt}{1em}\bodyfont\color{darktext} #1}}
\newcommand*{\skillsetstyle}[1]{{\fontsize{9pt}{1em}\bodyfontlight\color{graytext} #1}}

% Personal info commands
\newcommand*{\name}[2]{
    \def\@firstname{\headerfont #1}%
    \def\@lastname{\headerfont #2}
}
% legacy name helpers unused — removed

% Address
\newcommand*{\address}[1]{\def\@address{#1}}

% Position
\newcommand*{\position}[1]{\def\@position{#1}}

% Mobile
\newcommand*{\mobile}[1]{\def\@mobile{#1}}

% Email
\newcommand*{\email}[1]{\def\@email{#1}}

% Homepage
\newcommand*{\homepage}[1]{\def\@homepage{#1}}

% Github
\newcommand*{\github}[1]{\def\@github{#1}}
% LinkedIn
\newcommand*{\linkedin}[1]{\def\@linkedin{#1}}

% Helper macros
\newcommand{\acvHeaderNameDelim}{\space}
\newcommand{\acvHeaderAfterNameSkip}{.4mm}
% unused skip removed
\newcommand{\acvHeaderAfterAddressSkip}{-.5mm}
\newcommand{\acvHeaderIconSep}{\space}
\newcommand{\acvHeaderSocialSep}{\quad\textbar\quad}
\newcommand{\acvHeaderAfterSocialSkip}{6mm}
% unused skip removed

% Spacing
\newcommand{\acvSectionTopSkip}{3mm}
\newcommand{\acvSectionContentTopSkip}{2.5mm}

% Utilities
\newcolumntype{L}[1]{>{\raggedright\let\newline\\\arraybackslash\hspace{0pt}}m{#1}}
\newcolumntype{R}[1]{>{\raggedleft\let\newline\\\arraybackslash\hspace{0pt}}m{#1}}
\newcolumntype{P}[1]{>{\raggedright\let\newline\\\arraybackslash\hspace{0pt}}p{#1}}
\newcolumntype{T}[1]{>{\raggedleft\let\newline\\\arraybackslash\hspace{0pt}}p{#1}}

% Horizontal rule fill
\def\vhrulefill#1{\leavevmode\leaders\hrule\@height#1\hfill \kern\z@}

% conditional helper unused — removed

% CV structure — header
\newcommand*{\makecvheader}[1][C]{%
  \newlength{\headertextwidth}
  \setlength{\headertextwidth}{\textwidth}
  \begin{minipage}[c]{\headertextwidth}
    \ifthenelse{\equal{#1}{L}}{\raggedright}{\ifthenelse{\equal{#1}{R}}{\raggedleft}{\centering}}
    \headerfirstnamestyle{\@firstname}\headerlastnamestyle{{}\acvHeaderNameDelim\@lastname}%
    \\[\acvHeaderAfterNameSkip]%
    \ifthenelse{\isundefined{\@position}}{}{\headerpositionstyle{\@position}\\}%
    \ifthenelse{\isundefined{\@address}}{}{\headeraddressstyle{\@address\\[\acvHeaderAfterAddressSkip]}}%
    \headersocialstyle{%
      \newbool{isstart}%
      \setbool{isstart}{true}%
      \ifthenelse{\isundefined{\@mobile}}%
        {}%
        {%
          \href{tel:\@mobile}{\faMobile\acvHeaderIconSep\@mobile}%
          \setbool{isstart}{false}%
        }%
      \ifthenelse{\isundefined{\@email}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \href{mailto:\@email}{\faEnvelope\acvHeaderIconSep\@email}%
        }%
      \ifthenelse{\isundefined{\@homepage}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \href{http://\@homepage}{\faHome\acvHeaderIconSep\@homepage}%
        }%
      \ifthenelse{\isundefined{\@github}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \href{https://github.com/\@github}{\faGithubSquare\acvHeaderIconSep\@github}%
        }%
      \ifthenelse{\isundefined{\@linkedin}}%
        {}%
        {%
          \ifbool{isstart}{\setbool{isstart}{false}}{\acvHeaderSocialSep}%
          \href{https://www.linkedin.com/in/\@linkedin}{\faLinkedin\acvHeaderIconSep\@linkedin}%
        }%
    } \\[\acvHeaderAfterSocialSkip]%
  \end{minipage}
}

% Define a footer for CV
% Usage: \makecvfooter{<left>}{<center>}{<right>}
\newcommand*{\makecvfooter}[3]{%
  \fancyfoot{}
  \fancyfoot[L]{\footerstyle{#1}}
  \fancyfoot[C]{\footerstyle{#2}}
  \fancyfoot[R]{\footerstyle{#3}}
}

% Define a section for CV
% Usage: \cvsection{<section-title>}
\newcommand{\cvsection}[1]{%
  \vspace{\acvSectionTopSkip}
  \sectionstyle{#1}
  \phantomsection
  \color{sectiondivider}\vhrulefill{0.9pt}
}

% Define a paragraph for CV
\newenvironment{cvparagraph}{%
  \vspace{\acvSectionContentTopSkip}
  \vspace{-3mm}
  \paragraphstyle
}{%
  \par
}

% Define an environment for cventry
\newenvironment{cventries}{%
  \vspace{\acvSectionContentTopSkip}
  \begin{center}
}{%
  \end{center}
}

% Define an entry of cv information
% Usage: \cventry{<position>}{<title>}{<location>}{<date>}{<description>}
\newcommand*{\cventry}[5]{%
  \vspace{-1mm}
  \setlength\tabcolsep{0pt}
  \setlength{\extrarowheight}{0pt}
  \begin{tabular*}{\textwidth}{@{\extracolsep{\fill}} L{\textwidth - 5cm} R{5cm}}
    \entrytitlestyle{#2} & \entrylocationstyle{#3} \\
    \entrypositionstyle{#1} & \entrydatestyle{#4} \\
    \multicolumn{2}{L{\textwidth}}{\descriptionstyle{#5}}\\
  \end{tabular*}%
  % \vspace{3mm}
}

\newcommand*{\cvproject}[5]{%
  \setlength\tabcolsep{0pt}
  \setlength{\extrarowheight}{0pt}
  \begin{tabular*}{\textwidth}{@{\extracolsep{\fill}} L{\textwidth - 7cm} R{7cm}}
    \entrytitlestyle{#1} & \entrylocationstyle{#2} \\[2mm]
    \multicolumn{2}{L{\textwidth}}{\descriptionstyle{#3}}\\
    \multicolumn{2}{L{\textwidth}}{\metastyle{\textbf{\textit{Technologies:} #4}}} \\
    \multicolumn{2}{L{\textwidth}}{\metastyle{\textbf{\textit{URL:} #5}}} \\
  \end{tabular*}%
  \vspace{1mm}
}

% Define an environment for cvskill
\newenvironment{cvskills}{%
  \vspace{\acvSectionContentTopSkip}
  \vspace{-2.0mm}
  \begin{center}
    \setlength\tabcolsep{1ex}
    \setlength{\extrarowheight}{0pt}
    \begin{tabular*}{\textwidth}{@{\extracolsep{\fill}} T{\textwidth * \real{0.27}} P{\textwidth * \real{0.71}}}
}{%
    \end{tabular*}
  \end{center}
}
% Define a line of cv information(skill)
% Usage: \cvskill{<type>}{<skillset>}
\newcommand*{\cvskill}[2]{%
  \skilltypestyle{#1} & \skillsetstyle{#2} \\
}


% Define an environment for cvitems(for cventry)
\newenvironment{cvitems}{%
  \vspace{-4.0mm}
  \begin{justify}
  \begin{itemize}[leftmargin=2ex, nosep, noitemsep]
    \setlength{\parskip}{0pt}
    \renewcommand{\labelitemi}{\textbullet}
}{%
  \end{itemize}
  \end{justify}
  \vspace{-4.0mm}
}
