# Creates base machine for developing pivotal hadoop distribution
#
# docker build -t phdbase .

FROM ubuntu
MAINTAINER spaladugu@pivotal.io 

USER root
RUN echo root:cyborg | chpasswd

RUN apt-get update

RUN apt-get install -y openssh-server openssh-client apache2 supervisor dnsmasq dnsutils

#setup sshd 
RUN mkdir /var/run/sshd
RUN sed -i 's/PermitRootLogin without-password/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN sed 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' -i /etc/pam.d/sshd
ENV NOTVISIBLE "in users profile"
RUN echo "export VISIBLE=now" >> /etc/profile

#setup dnsmasq
RUN mkdir /etc/dnsmasq

COPY dnshosts /etc/dnsmasq/dnshosts
#setup supervisor
RUN mkdir -p /var/lock/apache2 /var/run/apache2 /var/run/sshd /var/log/supervisor
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 22 80

CMD ["/usr/bin/supervisord"]



