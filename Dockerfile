FROM thefab/autoclean-vsftpd
MAINTAINER Jean-Baptiste VESLIN <jean-baptiste.veslin@meteo.fr>

# AutocleanFtp variables for users creation must be empty.
# They will be defined on the fly with consul
# PYTHONUNBUFFERED is important for circus watchers logs
ENV DUPLICATORFTP_CONSUL=137.129.47.64:80 \
    DUPLICATORFTP_CIRCUS_LEVEL=error \
    DUPLICATORFTP_CIRCUS_MAX_AGE=310 \
    DUPLICATORFTP_CIRCUS_MAX_AGE_VARIANCE=30 \
    DUPLICATORFTP_CIRCUS_GRACEFUL_TIMEOUT=30 \
    DUPLICATORFTP_WATCHER_MAX_AGE=3600 \
    DUPLICATORFTP_LOG_LEVEL=debug \
    AUTOCLEANFTP_USERS= \
    AUTOCLEANFTP_PASSWORDS= \
    AUTOCLEANFTP_UIDS= \
    AUTOCLEANFTP_LIFETIMES= \
    AUTOCLEANFTP_LEVEL=silent \
    AUTOCLEANFTP_SYSLOG=0 \
    PYTHONUNBUFFERED=1

# Add runtime dependencies
ADD root/build/add_runtime_dependencies.sh /build/add_runtime_dependencies.sh
RUN /build/add_runtime_dependencies.sh

# Add build dependencies
ADD root/build/add_buildtime_dependencies.sh /build/add_buildtime_dependencies.sh
RUN /build/add_buildtime_dependencies.sh

# Install pip
ADD root/build/install_pip.sh /build/install_pip.sh
RUN /build/install_pip.sh

# Install python modules with pip (circus, requests)
ADD root/build/install_python_modules_with_pip.sh /build/install_python_modules_with_pip.sh
RUN /build/install_python_modules_with_pip.sh

# Add consul binaries
ADD root/build/add_consul_binary.sh /build/add_consul_binary.sh
ADD root/build/add_consul_cli.sh /build/add_consul_cli.sh
RUN /build/add_consul_binary.sh && \
    /build/add_consul_cli.sh

# Remove build dependencies
ADD root/build/remove_buildtime_dependencies.sh /build/remove_buildtime_dependencies.sh
RUN /build/remove_buildtime_dependencies.sh

# Add custom other files
COPY root /
