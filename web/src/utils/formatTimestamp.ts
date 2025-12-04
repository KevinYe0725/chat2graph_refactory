export const formatTimestamp = (formatMessage: (id: string, values?: any) => string, timestamp?: number) => {
    if (!timestamp) {
        return undefined;
    }
    const date = new Date(timestamp * 1000);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(today.getDate() - 1);

    const formatNumber = (n: number) => n < 10 ? '0' + n : n;

    if (date.toDateString() === today.toDateString()) {
        return formatMessage('home.today');
    } else if (date.toDateString() === yesterday.toDateString()) {
        return formatMessage('home.yesterday');
    } else {
        const month = formatNumber(date.getMonth() + 1);
        const day = formatNumber(date.getDate());
        return formatMessage('home.date', { month, day });
    }
}

