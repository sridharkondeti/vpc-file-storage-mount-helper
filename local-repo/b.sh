mkdir -p {RPMS,metadata}
cp $1 RPMS/
yum install createrepo -y
createrepo `pwd`
echo -e "[local-repo]\nname=Local YUM Repository\nbaseurl=file://`pwd`\nenabled=1\ngpgcheck=0" > /etc/yum.repos.d/local-repo.repo
yum makecache
