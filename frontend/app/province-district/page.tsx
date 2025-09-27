'use client';
import React, { useEffect, useState, Fragment } from 'react';
import { Card, Table, Row, Col, Breadcrumb, Spin, Select, Space, Typography } from 'antd';
import { DatabaseOutlined} from '@ant-design/icons';
import { API_BASE, apiForm } from '@/lib/api';
import type { TableProps } from 'antd';

export default function ProvinceDistrict() {
	const [isLoading, setIsLoading] = useState(false);
	const [orderField, setOrderField] = useState('province_id');
	const [orderType, setOrderType] = useState('asc');
	const [dataSource, setDataSource] = useState<any[]>([]);
	const [dataProvince, setDataProvince] = useState<any[]>([]);
	const [dataDistrict, setDataDistrict] = useState<any[]>([]);
	const [filterOption, setFilterOption] = useState({
		province_id : 'all',
		district_id : 'all',
	});
	const [page, setPage] = useState(1);
  	const [pageSize, setPageSize] = useState(10);



	async function refresh(p=page, ps=pageSize, order_by=orderField, order_type=orderType, province_id=filterOption.province_id, district_id=filterOption.district_id, init: RequestInit = {}) {
		try {
			setIsLoading(true);
			const res = await fetch(`${API_BASE}/list_province_district?page=${p}&page_size=${ps}&order_by=${order_by}&order_type=${order_type}&province_id=${province_id}&district_id=${district_id}`, { 
				cache: "no-store",
				credentials: 'include',
				headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
				...init,
			});

			setDataSource(await res.json());
		} catch (e: any) {
			setIsLoading(false);
		} finally {
			setIsLoading(false);
		}
	}

	const onChangeTable: TableProps<DataType>['onChange'] = (pagination, filters, sorter:any, extra) => {
		if(extra.action == 'sort') {
			if(typeof sorter.order !== 'undefined') {
				setPage(1);
				setOrderField(sorter.field)
				setOrderType((sorter.order == 'descend' ? 'desc' : 'asc'))
			} else {
				setPage(1);
				setOrderField('province_id')
				setOrderType('asc')
			}
		}

	};

	useEffect(() => {
		refresh();
	}, [page, pageSize, orderField, orderType, filterOption])

	useEffect(() => {
		async function fetchProvince(init: RequestInit = {}) {
			try {
				const res = await fetch(`${API_BASE}/list_province`, { 
					cache: "no-store",
					credentials: 'include',
					headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
					...init,
				});

				const dataOption = await res.json()
				

				if(dataOption.total > 0) {
					setDataProvince([{
						value: "all",
						label: "ทั้งหมด (All)",
					}, ...dataOption.items.map((ele:any) => {
						return {
							value: ele.province_id,
							label: ele.province_name + ' (' + ele.province_name_en+ ')',
						}
					})]);
				} else {
					setDataProvince([]);
				}
			} catch (e: any) {
				setDataProvince([]);
			}
		}

		async function fetchDistrict(init: RequestInit = {}) {
			try {
				const res = await fetch(`${API_BASE}/list_district`, { 
					cache: "no-store",
					credentials: 'include',
					headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
					...init,
				});

				const dataOption = await res.json()
				if(dataOption.total > 0) {
					setDataDistrict([{
						value: "all",
						label: "ทั้งหมด (All)",
					}, ...dataOption.items.map((ele:any) => {
						return {
							value: ele.district_id,
							label: ele.district_name + ' (' + ele.district_name_en+ ')',
						}
					})]);
				} else {
					setDataDistrict([]);
				}
			} catch (e: any) {
				setDataDistrict([]);
			}
		}

		fetchProvince();
		fetchDistrict();

	}, [])

	const handleChangeProvince = (value: { value: string; label: React.ReactNode }) => {
		setFilterOption({
			province_id : value,
			district_id : filterOption.district_id,
		})
		setPage(1);
	}

	const handleChangeDistrict = (value: { value: string; label: React.ReactNode }) => {
		setFilterOption({
			province_id : filterOption.province_id,
			district_id : value,
		})
		setPage(1);
	}

	
	return (
		<Fragment>
			<Breadcrumb className="breadcrumb-design" separator={`>`}
				items={[{ title: 'Home', path: '/', }, { title: 'Province / District' }]}
			/>
			<div className="block-content">
				<Row gutter={[16, 16]}>
					<Col span={24}>
						<Spin spinning={isLoading} size={`large`}>
							<Card title={<span><DatabaseOutlined /> Province / District</span>}>
								
								<Row gutter={[24, 24]}>
									<Col span={24} align={`right`}>
										<Space size={`large`}>

											<Space>
												<Typography.Text>จังหวัด (Province) : </Typography.Text>
												<Select
													showSearch
													filterOption={(input, option) => (option?.label?.toLowerCase() ?? '').includes(input?.toLowerCase())}
													defaultValue={{ value: 'all', label: 'ทั้งหมด (All)' }}
													options={dataProvince}
													style={{ width: 250, textAlign: `left` }}
													onChange={handleChangeProvince}
												/>
											</Space>

											<Space>
												<Typography.Text>อำเภอ (District) : </Typography.Text>
												<Select
													showSearch
													filterOption={(input, option) => (option?.label?.toLowerCase() ?? '').includes(input?.toLowerCase())}
													defaultValue={{ value: 'all', label: 'ทั้งหมด (All)' }}
													options={dataDistrict}
													style={{ width: 350, textAlign: `left` }}
													onChange={handleChangeDistrict}
												/>
											</Space>
											
										</Space>
									</Col>
									<Col span={24}>
										<Table
											rowKey="id"
											dataSource={dataSource.items}
											columns={[
												{ 
													title: 'No.', 
													align:'center', 
													width: 50, 
													render: (value:string, record:any, index:number) => {
														return (((dataSource.page - 1) * dataSource.page_size) + (index + 1)).toLocaleString();
													}
												},
												{ 
													title: 'จังหวัด (Province)', 
													dataIndex: 'province_name',
													sortDirections: ['ascend', 'descend'],
													width: 400,
													sorter: true,
													render: (value:string, record:any) => {
														return record.province_name + ' (' + record.province_name_en + ')'
													} 
												},
												{ 
													title: 'อำเภอ (District)', 
													dataIndex: 'district_name',
													sortDirections: ['ascend', 'descend'],
													sorter: true,
													width: 400,
													render: (value:string, record:any) => {
														return record.district_name + ' (' + record.district_name_en + ')'
													}
												},
											]}
											pagination={{
												simple:true,
												current: parseInt(dataSource?.page),
												pageSize: parseInt(dataSource?.page_size),
												total: parseInt(dataSource?.total),
												showSizeChanger: true,
												showTotal: (total:number) => {
													return `จำนวนทั้งหมด (Total) ${total.toLocaleString()} รายการ (Items)`
												},
												onChange: (p:number, ps:number) => {
													setPage(p);
													setPageSize(ps);
												},
												locale: {items_per_page: "หน้า (Page)"}
											}}
											onChange={onChangeTable}
										/>
									</Col>
								</Row>
									
							</Card>
						</Spin>
					</Col>
				</Row>
			</div>
		</Fragment>
	);
}