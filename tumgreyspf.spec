%define name    tumgreyspf
%define version 1.00
%define release 1
%define prefix  %{_prefix}

Summary:       Powerful, easy to use spam protection.
Name:          %{name}
Version:       %{version}
Release:       %{release}
Copyright:     tummy.com, ltd.
Group:         Applications/System
URL:           http://www.tummy.com/krud/
Source:        %{name}-%{version}.tar.gz
Packager:      Sean Reifschneider <jafo-rpms@tummy.com>
BuildRoot:     /var/tmp/%{name}-root
Requires:      python
Requires:      postfix >= 2.1
BuildArch:     noarch

%description
This is tumgreyspf, an external policy checker for the postfix mail
server.  It can optionally greylist and/or use spfquery to check SPF
records to determine if email should be accepted by your server.

Because of it's design, legitimate e-mail is never trapped or rejected.
Only spam and viruses are caught.  Since adding it to our mail server
(which also uses Spam Assassin, ClamAV, and an outsourced anti-spam
system), our spam level has dropped by an order of magnitude.

It uses the file-system as it's database, no additional database is
required to use it.

%prep
%setup
%build

%install
[ -n "$RPM_BUILD_ROOT" -a "$RPM_BUILD_ROOT" != / ] && rm -rf "$RPM_BUILD_ROOT"

#  make directories
mkdir -p "$RPM_BUILD_ROOT"/usr/lib/tumgreyspf/
mkdir -p "$RPM_BUILD_ROOT"/var/lib/tumgreyspf/config
mkdir -p "$RPM_BUILD_ROOT"/var/lib/tumgreyspf/data
mkdir -p "$RPM_BUILD_ROOT"/usr/sbin
mkdir -p "$RPM_BUILD_ROOT"/etc/cron.d

#  copy over files
for file in tumgreyspf tumgreyspf-clean tumgreyspf-configtest \
      tumgreyspf-install tumgreyspf-stat tumgreyspfsupp.py
do
   cp "$file" "$RPM_BUILD_ROOT"/usr/lib/tumgreyspf/
done
cp tumgreyspf.conf "$RPM_BUILD_ROOT"/var/lib/tumgreyspf/config/
cp __default__.dist "$RPM_BUILD_ROOT"/var/lib/tumgreyspf/config/__default__

#  link external programs to /usr/sbin
ln -s /usr/lib/tumgreyspf/tumgreyspf-configtest "$RPM_BUILD_ROOT"/usr/sbin
ln -s /usr/lib/tumgreyspf/tumgreyspf-stat "$RPM_BUILD_ROOT"/usr/sbin

#  set up crontab
echo '0 0 * * * nobody /usr/lib/tumgreyspf/tumgreyspf-clean' \
      >"$RPM_BUILD_ROOT"/etc/cron.d/tumgreyspf

#  replace pieces in code that need to reflect new directories
(
   cd "$RPM_BUILD_ROOT"/usr/lib/tumgreyspf/
   sed 's|^sys.path.append.*|sys.path.append("/usr/lib/tumgreyspf")|' \
      tumgreyspf >tumgreyspf.new && \
      cat tumgreyspf.new >tumgreyspf && \
      rm -f tumgreyspf.new
   sed 's|^sys.path.append.*|sys.path.append("/usr/lib/tumgreyspf")|' \
      tumgreyspf-clean >tumgreyspf-clean.new && \
      cat tumgreyspf-clean.new >tumgreyspf-clean && \
      rm -f tumgreyspf-clean.new
   sed 's|^sys.path.append.*|sys.path.append("/usr/lib/tumgreyspf")|' \
      tumgreyspf-stat >tumgreyspf-stat.new && \
      cat tumgreyspf-stat.new >tumgreyspf-stat && \
      rm -f tumgreyspf-stat.new
   sed 's|^defaultConfigFilename.*|defaultConfigFilename = "/var/lib/tumgreyspf/config/tumgreyspf.conf"|' \
      tumgreyspfsupp.py >tumgreyspfsupp.py.new && \
      cat tumgreyspfsupp.py.new >tumgreyspfsupp.py && \
      rm -f tumgreyspfsupp.py.new

   cd "$RPM_BUILD_ROOT"/var/lib/tumgreyspf/config/
   sed 's|^spfqueryPath.*|spfqueryPath = "/usr/bin/spfquery"|' \
      tumgreyspf.conf | \
      sed 's|^greylistDir.*|greylistDir = "/var/lib/tumgreyspf/data"|' | \
      sed 's|^configPath.*|configPath = "file:///var/lib/tumgreyspf/config"|' \
      >tumgreyspf.conf.new && \
      cat tumgreyspf.conf.new >tumgreyspf.conf && \
      rm -f tumgreyspf.conf.new
)

%clean
[ -n "$RPM_BUILD_ROOT" -a "$RPM_BUILD_ROOT" != / ] && rm -rf "$RPM_BUILD_ROOT"

%files
%defattr(755,root,root)
/usr/lib/tumgreyspf
%dir /var/lib/tumgreyspf
%dir /var/lib/tumgreyspf/config
%config /var/lib/tumgreyspf/config/tumgreyspf.conf
%config /var/lib/tumgreyspf/config/__default__
%attr(700,nobody,root) /var/lib/tumgreyspf/data
/etc/cron.d/tumgreyspf
%doc README README.QuickStart README.performance WHATSNEW TODO
